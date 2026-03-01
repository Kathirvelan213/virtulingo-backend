"""
DialogueOrchestrator — coordinates the real-time STT → Grammar + LLM → TTS workflow.

This service implements the parallel processing pattern from the system design:
  1. Streaming STT: Audio → Text (streaming transcription)
  2. Orchestrator: Once utterance complete, triggers:
     - Conversation Engine (LLM for NPC response) → PRIMARY PATH
     - Grammar Correction Engine → PARALLEL, ASYNC
  3. Streaming TTS: LLM text stream → Audio stream → Unity client

Key Design Principles:
- Grammar correction NEVER blocks the conversation flow
- LLM and TTS use streaming to minimize latency
- Event-driven architecture for scalability
- Context is injected from Redis world state
"""
import asyncio
import json
from typing import AsyncGenerator, Optional, Callable
from datetime import datetime

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel
from domain.interfaces.ISpeechToText import ISpeechToText
from domain.interfaces.ITextToSpeech import ITextToSpeech
from domain.interfaces.IRepositories import (
    IWorldStateRepository,
    IMistakeRepository,
    INPCRepository,
    IPlayerProfileRepository,
)
from domain.models import ConversationTurn


_GRAMMAR_SYSTEM_PROMPT = """
You are an expert {target_language} language teacher analyzing a student's speech.

Return ONLY valid JSON with this exact schema (no extra text):
{{
  "mistake_found": bool,
  "category": "verb_conjugation | gender_agreement | tense | vocabulary | pronunciation_flag | none",
  "original": "the incorrect phrase",
  "correction": "the corrected version",
  "explanation": "1-sentence pedagogical explanation in English",
  "severity": 1-5
}}

Student utterance: "{utterance}"

Be strict but fair. Do not invent mistakes. If perfect, set mistake_found to false.
"""

_NPC_SYSTEM_PROMPT = """
You are {npc_name}, {npc_personality}. {npc_backstory}

WORLD CONTEXT:
- Scene: {scene_id}
- Player is holding: {object_in_hand}
- Active quest: {active_quest}
- Your relationship with the player: {relationship_score}/10 (0=stranger, 10=best friend)

LINGUISTIC RULES:
- Respond ONLY in {target_language}. NEVER use English.
- Match CEFR level: {npc_cefr}
- Keep responses conversational and concise (2-4 sentences max)
- Adapt to player's proficiency level ({proficiency_level})
  - If they speak simply, use simpler vocabulary and grammar
  - If they speak fluently, respond naturally at your CEFR level
- Stay in character. NEVER correct their grammar explicitly.
- React to both their words AND the world context

EMOTIONAL TONE: {emotional_tone}

RECENT CONVERSATION:
{conversation_history}

Respond naturally as {npc_name}.
"""


class DialogueOrchestrator:
    """
    Coordinates the full STT → LLM + Grammar → TTS conversation pipeline.
    
    This orchestrator implements the event-driven pattern:
    - Main path: STT → LLM → TTS (streaming, low latency)
    - Parallel path: Grammar correction (async, non-blocking)
    """
    
    def __init__(
        self,
        world_state_repo: IWorldStateRepository,
        mistake_repo: IMistakeRepository,
        npc_repo: INPCRepository,
        player_profile_repo: IPlayerProfileRepository,
        stt_service: ISpeechToText,
        tts_service: ITextToSpeech,
        llm_service: ILargeLanguageModel,
        event_callback: Optional[Callable] = None,
    ):
        self._world_state = world_state_repo
        self._mistakes = mistake_repo
        self._npcs = npc_repo
        self._players = player_profile_repo
        self._stt = stt_service
        self._tts = tts_service
        self._llm = llm_service
        self._event_callback = event_callback  # For broadcasting events (grammar corrections, etc.)

    # ============================================================================
    # PRIMARY WORKFLOW: Full Conversation Round-Trip
    # ============================================================================

    async def process_conversation_turn(
        self,
        player_id: str,
        npc_id: str,
        audio_bytes: bytes,
    ) -> AsyncGenerator[bytes | dict, None]:
        """
        Full conversation pipeline:
        1. STT: Transcribe player audio
        2. Parallel execution:
           - Grammar correction (async, non-blocking) → fires event
           - LLM conversation → TTS → yields audio chunks
        3. Persist conversation turn
        
        Yields:
            - Audio chunks (bytes) from TTS for streaming to Unity client
            - Metadata dicts: {"type": "transcription", "text": "..."} or {"type": "npc_text", "text": "..."}
        """
        print(f"[Orchestrator] Starting conversation turn for player={player_id}, npc={npc_id}")
        
        # Step 1: Transcribe audio to text
        print(f"[Orchestrator] Step 1: Getting player state...")
        state = await self._world_state.get_player_state(player_id)
        language = state.get("language", "fr")
        
        print(f"[Orchestrator] Step 1: Transcribing {len(audio_bytes)} bytes of audio (language={language})...")
        player_text = await self._stt.transcribe(audio_bytes, language=language)
        print(f"[Orchestrator] Transcription result: '{player_text}'")
        
        if not player_text.strip():
            print("[Orchestrator] No speech detected, returning")
            return  # No speech detected
        
        # Yield transcription
        yield {"type": "transcription", "text": player_text}
        
        # Step 2: Persist player's turn
        print(f"[Orchestrator] Step 2: Persisting player turn...")
        await self._world_state.append_conversation_turn(
            player_id, npc_id, "player", player_text
        )
        
        # Step 3: Fire grammar correction in background (non-blocking)
        print(f"[Orchestrator] Step 3: Starting grammar correction task...")
        asyncio.create_task(
            self._process_grammar_correction_async(player_id, player_text, language)
        )
        
        # Step 4: Generate NPC response (streaming LLM → streaming TTS)
        print(f"[Orchestrator] Step 4: Generating NPC response stream...")
        npc_reply_parts = []
        
        chunk_num = 0
        async for audio_chunk in self._generate_npc_response_stream(
            player_id, npc_id, player_text, state, npc_reply_parts
        ):
            chunk_num += 1
            print(f"[Orchestrator] Yielding audio chunk #{chunk_num} ({len(audio_chunk)} bytes)")
            yield audio_chunk
        
        print(f"[Orchestrator] Total chunks yielded: {chunk_num}")
        
        # Yield complete NPC text response
        npc_full_text = "".join(npc_reply_parts)
        print(f"[Orchestrator] NPC complete response: '{npc_full_text}'")
        yield {"type": "npc_text", "text": npc_full_text}
        
        # Step 5: Persist NPC's turn after streaming completes
        full_npc_reply = "".join(npc_reply_parts)
        print(f"[Orchestrator] Step 5: Persisting NPC reply: '{full_npc_reply[:100]}...'")
        await self._world_state.append_conversation_turn(
            player_id, npc_id, "npc", full_npc_reply
        )
        
        print("[Orchestrator] Conversation turn complete")

    async def process_streaming_conversation(
        self,
        player_id: str,
        npc_id: str,
        audio_stream: AsyncGenerator[bytes, None],
    ) -> AsyncGenerator[bytes, None]:
        """
        Streaming variant: processes audio chunks as they arrive.
        
        This enables true real-time transcription with streaming STT services
        like Deepgram that support incremental transcription.
        
        Args:
            audio_stream: Async generator yielding audio chunks from Unity
        
        Yields:
            NPC audio response chunks
        """
        state = await self._world_state.get_player_state(player_id)
        language = state.get("language", "fr")
        
        # Step 1: Streaming STT
        transcript_parts = []
        async for text_chunk in self._stt.transcribe_stream(audio_stream, language=language):
            transcript_parts.append(text_chunk)
        
        player_text = " ".join(transcript_parts).strip()
        
        if not player_text:
            return
        
        # Step 2-5: Same as process_conversation_turn
        await self._world_state.append_conversation_turn(
            player_id, npc_id, "player", player_text
        )
        
        asyncio.create_task(
            self._process_grammar_correction_async(player_id, player_text, language)
        )
        
        npc_reply_parts = []
        async for audio_chunk in self._generate_npc_response_stream(
            player_id, npc_id, player_text, state, npc_reply_parts
        ):
            yield audio_chunk
        
        full_npc_reply = "".join(npc_reply_parts)
        await self._world_state.append_conversation_turn(
            player_id, npc_id, "npc", full_npc_reply
        )

    # ============================================================================
    # PRIVATE HELPERS: NPC Response Generation
    # ============================================================================

    async def _generate_npc_response_stream(
        self,
        player_id: str,
        npc_id: str,
        player_text: str,
        state: dict,
        reply_collector: list,
    ) -> AsyncGenerator[bytes, None]:
        """
        Core streaming pipeline: LLM → TTS
        
        1. Fetch context (NPC profile, conversation history)
        2. Build dynamic system prompt
        3. Stream LLM response text
        4. Stream text chunks to TTS
        5. Yield audio chunks as they're generated
        """
        # Fetch all context in parallel
        npc_profile, history, player_profile = await asyncio.gather(
            self._npcs.get_npc_profile(npc_id),
            self._world_state.get_conversation_history(player_id, npc_id, window=10),
            self._players.get_profile(player_id),
        )
        
        # Build dynamic system prompt with context injection
        system_prompt = self._build_npc_system_prompt(
            npc_profile, state, player_profile, history
        )
        
        # Stream LLM response
        llm_stream = self._llm.stream_complete(system_prompt, player_text)
        
        # Create a generator that collects LLM chunks while passing them through
        async def _llm_with_collection() -> AsyncGenerator[str, None]:
            async for chunk in llm_stream:
                reply_collector.append(chunk)
                yield chunk
        
        # Stream to TTS and yield audio chunks
        voice_id = npc_profile.get("voice_id", "")
        async for audio_chunk in self._tts.synthesize_stream(
            _llm_with_collection(), voice_id
        ):
            yield audio_chunk

    def _build_npc_system_prompt(
        self,
        npc_profile: dict,
        state: dict,
        player_profile: dict,
        history: list,
    ) -> str:
        """
        Dynamically assembles the NPC system prompt with real-time context injection.
        """
        history_text = "\n".join(
            f"{'PLAYER' if t['role'] == 'player' else npc_profile['name'].upper()}: {t['content']}"
            for t in history
        ) or "(First interaction)"
        
        return _NPC_SYSTEM_PROMPT.format(
            npc_name=npc_profile["name"],
            npc_personality=npc_profile["personality"],
            npc_backstory=npc_profile["backstory"],
            scene_id=state.get("scene_id", "unknown"),
            object_in_hand=state.get("object_in_hand") or "nothing",
            active_quest=state.get("active_quest") or "none",
            relationship_score=int(npc_profile.get("relationship_score", 0.0) * 10),
            target_language=state.get("language", "French"),
            npc_cefr=npc_profile.get("language_complexity", "B1"),
            emotional_tone=npc_profile.get("emotional_tone", "neutral"),
            proficiency_level=player_profile.get("proficiency_level", "A2"),
            conversation_history=history_text,
        )

    # ============================================================================
    # GRAMMAR CORRECTION: Parallel, Non-Blocking Path
    # ============================================================================

    async def _process_grammar_correction_async(
        self,
        player_id: str,
        player_text: str,
        language: str,
    ) -> None:
        """
        Background task: analyzes player's utterance for grammar mistakes.
        
        This runs in parallel with the main conversation flow and:
        1. Calls LLM with structured JSON output
        2. Persists mistake to database if found
        3. Broadcasts event via callback (for WebSocket push to Unity)
        
        Failures are caught and logged — grammar correction must never crash the game.
        """
        try:
            system_prompt = _GRAMMAR_SYSTEM_PROMPT.format(
                target_language=language.capitalize(),
                utterance=player_text,
            )
            
            raw_result = await self._llm.complete(system_prompt, "Analyze the utterance above.")
            result = json.loads(raw_result)
            
            if result.get("mistake_found"):
                # Persist to database
                await self._mistakes.log_mistake(
                    player_id=player_id,
                    category=result.get("category", "unknown"),
                    original=result.get("original", player_text),
                    correction=result.get("correction", ""),
                    explanation=result.get("explanation", ""),
                )
                
                # Broadcast event (for WebSocket notification to Unity)
                if self._event_callback:
                    await self._event_callback({
                        "type": "grammar_correction",
                        "player_id": player_id,
                        "data": result,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        
        except Exception as e:
            # Grammar correction failures must not interrupt gameplay
            print(f"[DialogueOrchestrator] Grammar correction failed (non-fatal): {e}")

    # ============================================================================
    # EXPLICIT GRAMMAR CHECK (for REST API)
    # ============================================================================

    async def get_grammar_correction(
        self,
        player_id: str,
        player_text: str,
        language: str = "French",
    ) -> dict:
        """
        Synchronous grammar correction for explicit REST API calls.
        Used when Unity explicitly requests grammar feedback outside the live flow.
        """
        system_prompt = _GRAMMAR_SYSTEM_PROMPT.format(
            target_language=language,
            utterance=player_text,
        )
        
        raw_result = await self._llm.complete(system_prompt, "Analyze the utterance above.")
        result = json.loads(raw_result)
        
        # Optionally persist the mistake
        if result.get("mistake_found"):
            await self._mistakes.log_mistake(
                player_id=player_id,
                category=result.get("category", "unknown"),
                original=result.get("original", player_text),
                correction=result.get("correction", ""),
                explanation=result.get("explanation", ""),
            )
        
        return result
