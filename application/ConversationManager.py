"""
ConversationManager — core application orchestrator for the real-time conversation loop.

Flow:
  1. Transcribe player audio via STT
  2. Fetch world state and NPC profile from repositories
  3. Assemble dynamic LLM system prompt (context injection)
  4. Stream LLM reply → stream to TTS → yield audio chunks
  5. Store conversation turn in Redis history
  6. Fire grammar correction (parallel, non-blocking)

The manager is framework-agnostic. The router streams audio chunks to Unity via WebSocket.
"""
import asyncio
import json
from typing import AsyncGenerator

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel
from domain.interfaces.ISpeechToText import ISpeechToText
from domain.interfaces.ITextToSpeech import ITextToSpeech
from domain.interfaces.IRepositories import (
    IWorldStateRepository,
    IMistakeRepository,
    INPCRepository,
    IPlayerProfileRepository,
)


_GRAMMAR_CORRECTION_SYSTEM_PROMPT = """
You are an expert {target_language} language teacher.
Analyze the student's utterance and return a JSON object with this exact schema:
{{
  "mistake_found": bool,
  "category": "verb_conjugation | gender_agreement | tense | vocabulary | pronunciation_flag | none",
  "original": "the incorrect phrase the student said",
  "correction": "the corrected version",
  "explanation": "short 1-sentence pedagogical explanation in English",
  "severity": 1-5
}}
If no mistake is found, return {{"mistake_found": false, "category": "none", "original": "", "correction": "", "explanation": "", "severity": 0}}.
Be strict but helpful. Do not invent mistakes.
"""

_NPC_SYSTEM_PROMPT = """
You are {npc_name}, {npc_personality}. {npc_backstory}

WORLD CONTEXT:
- Scene: {scene_id}
- Player is holding: {object_in_hand}
- Active quest: {active_quest}
- Your relationship with the player: {relationship_score} (-1=stranger/hostile, 0=neutral, 1=close friend)

CONVERSATION RULES:
- Always respond ONLY in {target_language}. Never switch to English.
- Match your vocabulary and grammar complexity to CEFR level: {npc_cefr}
- Reflect your emotional tone: {emotional_tone}
- Keep responses concise and immersive (2-4 sentences max).
- ADAPT to the player's language level. If they speak simply ({proficiency_level}), 
  use simpler words and shorter sentences. If they speak fluently, elevate your language.
- Do NOT correct the player. Stay in character always.
- React naturally to what they said and what they are holding or doing.

CONVERSATION HISTORY:
{conversation_history}
"""


class ConversationManager:
    def __init__(
        self,
        world_state_repo: IWorldStateRepository,
        mistake_repo: IMistakeRepository,
        npc_repo: INPCRepository,
        player_profile_repo: IPlayerProfileRepository,
        stt_service: ISpeechToText,
        tts_service: ITextToSpeech,
        llm_service: ILargeLanguageModel,
    ):
        self._world_state = world_state_repo
        self._mistakes = mistake_repo
        self._npcs = npc_repo
        self._players = player_profile_repo
        self._stt = stt_service
        self._tts = tts_service
        self._llm = llm_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_utterance_stream(
        self, player_id: str, npc_id: str, audio_bytes: bytes
    ) -> AsyncGenerator[bytes, None]:
        """
        Full conversational round-trip.
        - Transcribes audio
        - Fires grammar correction in background (non-blocking)
        - Streams NPC audio reply chunks to caller
        """
        # 1. Transcribe
        state = await self._world_state.get_player_state(player_id)
        language = state.get("language", "fr")
        player_text = await self._stt.transcribe(audio_bytes, language=language)

        if not player_text.strip():
            return  # Nothing to respond to

        # 2. Persist player turn to history
        await self._world_state.append_conversation_turn(player_id, npc_id, "player", player_text)

        # 3. Fire grammar correction as background task (does not block audio)
        asyncio.create_task(
            self._run_grammar_correction(player_id, player_text, language)
        )

        # 4. Assemble NPC prompt and stream response
        system_prompt = await self._build_npc_prompt(player_id, npc_id, state)
        llm_stream = self._llm.stream_complete(system_prompt, player_text)

        # 5. Pipe LLM text stream → TTS audio stream → yield chunks
        npc_reply_parts = []

        async def _llm_with_collection() -> AsyncGenerator[str, None]:
            async for chunk in llm_stream:
                npc_reply_parts.append(chunk)
                yield chunk

        npc_profile = await self._npcs.get_npc_profile(npc_id)
        voice_id = npc_profile.get("voice_id", "")

        async for audio_chunk in self._tts.synthesize_stream(_llm_with_collection(), voice_id):
            yield audio_chunk

        # 6. Persist NPC turn after streaming is done
        full_reply = "".join(npc_reply_parts)
        await self._world_state.append_conversation_turn(player_id, npc_id, "npc", full_reply)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_npc_prompt(
        self, player_id: str, npc_id: str, state: dict
    ) -> str:
        npc_profile, history, player_profile = await asyncio.gather(
            self._npcs.get_npc_profile(npc_id),
            self._world_state.get_conversation_history(player_id, npc_id, window=10),
            self._players.get_profile(player_id),
        )

        # Format conversation history as a readable dialogue
        history_text = "\n".join(
            f"{'PLAYER' if t['role'] == 'player' else npc_profile['name'].upper()}: {t['content']}"
            for t in history
        ) or "(No previous conversation)"

        return _NPC_SYSTEM_PROMPT.format(
            npc_name=npc_profile["name"],
            npc_personality=npc_profile["personality"],
            npc_backstory=npc_profile["backstory"],
            scene_id=state.get("scene_id", "unknown"),
            object_in_hand=state.get("object_in_hand") or "nothing",
            active_quest=state.get("active_quest") or "none",
            relationship_score=npc_profile.get("relationship_score", 0.0),
            target_language=state.get("language", "fr"),
            npc_cefr=npc_profile["language_complexity"],
            emotional_tone=npc_profile["emotional_tone"],
            proficiency_level=player_profile.get("proficiency_level", "A2"),
            conversation_history=history_text,
        )

    async def _run_grammar_correction(
        self, player_id: str, player_text: str, target_language: str
    ) -> None:
        """
        Parallel background task: call LLM for grammar analysis and persist the result.
        Failures are silently logged — grammar correction must never crash the game loop.
        """
        try:
            system_prompt = _GRAMMAR_CORRECTION_SYSTEM_PROMPT.format(
                target_language=target_language
            )
            raw_result = await self._llm.complete(system_prompt, player_text)
            result = json.loads(raw_result)

            if result.get("mistake_found"):
                await self._mistakes.log_mistake(
                    player_id=player_id,
                    category=result.get("category", "unknown"),
                    original=result.get("original", player_text),
                    correction=result.get("correction", ""),
                    explanation=result.get("explanation", ""),
                )
        except Exception as e:
            # Grammar correction must not interrupt gameplay
            print(f"[GrammarCorrection] Non-fatal error for player {player_id}: {e}")

    async def get_grammar_correction_result(
        self, player_id: str, player_text: str, target_language: str
    ) -> dict:
        """
        Synchronous grammar correction — used by the GrammarManager for the
        REST endpoint that explicitly polls for a correction.
        """
        system_prompt = _GRAMMAR_CORRECTION_SYSTEM_PROMPT.format(
            target_language=target_language
        )
        raw = await self._llm.complete(system_prompt, player_text)
        return json.loads(raw)
