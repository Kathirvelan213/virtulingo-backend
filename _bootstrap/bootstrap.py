"""
Dependency Injection Container — bootstrap wiring of all concrete implementations.

Pure Python, no FastAPI imports. All infrastructure is instantiated here
and wired into application-layer managers.

Configuration:
- LLM: Gemini (Google)
- STT: Local Whisper (faster-whisper)
- TTS: Local Coqui TTS
"""
from application.ConversationManager import ConversationManager
from application.GrammarManager import GrammarManager
from application.WorldStateManager import WorldStateManager
from application.ReviewScheduler import ReviewScheduler
from application.DialogueOrchestrator import DialogueOrchestrator

from infrastructures.GeminiLLM import GeminiLLM
from infrastructures.SpeechToText import WhisperSTT
from infrastructures.TextToSpeech import CoquiTTS
from infrastructures.repos.WorldStateRepo import RedisWorldStateRepository
from infrastructures.repos.MistakeRepo import PostgresMistakeRepository
from infrastructures.repos.NPCRepo import PostgresNPCRepository
from infrastructures.repos.PlayerProfileRepo import InMemoryPlayerProfileRepository
from infrastructures.events import EventBus


class Container:
    def __init__(self):
        try:
            # ── Infrastructure: Event Bus ────────────────────────────────
            self.event_bus = EventBus()
            print("[Container] Event bus initialized")
            
            # ── Infrastructure: AI services ──────────────────────────────
            # LLM: Gemini (Google)
            print("[Container] Initializing Gemini LLM...")
            self.llm_service = GeminiLLM()
            print("[Container] ✓ Gemini LLM initialized")
            
            # STT: Local Whisper (faster-whisper)
            print("[Container] Initializing Whisper STT...")
            self.stt_service = WhisperSTT()
            print("[Container] ✓ Whisper STT initialized")
            
            # TTS: Local Coqui TTS
            print("[Container] Initializing Coqui TTS...")
            self.tts_service = CoquiTTS()
            print("[Container] ✓ Coqui TTS initialized")

            # ── Infrastructure: Repositories ─────────────────────────────
            print("[Container] Initializing Redis repository...")
            self.world_state_repo = RedisWorldStateRepository()
            print("[Container] ✓ Redis repository initialized")
            
            print("[Container] Initializing PostgreSQL repositories...")
            self.mistake_repo = PostgresMistakeRepository()
            self.npc_repo = PostgresNPCRepository()
            self.player_profile_repo = InMemoryPlayerProfileRepository()
            print("[Container] ✓ PostgreSQL repositories initialized")

            # ── Application: Managers (DI injected) ──────────────────────
            self.conversation_manager = ConversationManager(
                world_state_repo=self.world_state_repo,
                mistake_repo=self.mistake_repo,
                npc_repo=self.npc_repo,
                player_profile_repo=self.player_profile_repo,
                stt_service=self.stt_service,
                tts_service=self.tts_service,
                llm_service=self.llm_service,
            )

            self.grammar_manager = GrammarManager(
                llm_service=self.llm_service,
                mistake_repo=self.mistake_repo,
            )

            self.world_state_manager = WorldStateManager(
                world_state_repo=self.world_state_repo,
            )

            self.review_scheduler = ReviewScheduler(
                llm_service=self.llm_service,
                mistake_repo=self.mistake_repo,
            )
            
            # ── Application: DialogueOrchestrator (Main Workflow) ────────
            # Implements the STT → Grammar + LLM → TTS workflow
            async def event_callback(event: dict):
                """Callback for broadcasting events to the event bus."""
                await self.event_bus.publish(
                    topic=event.get("type", "unknown"),
                    event_type=event.get("type"),
                    data=event.get("data", {}),
                    metadata={
                        "player_id": event.get("player_id"),
                        "timestamp": event.get("timestamp"),
                    },
                )
            
            self.dialogue_orchestrator = DialogueOrchestrator(
                world_state_repo=self.world_state_repo,
                mistake_repo=self.mistake_repo,
                npc_repo=self.npc_repo,
                player_profile_repo=self.player_profile_repo,
                stt_service=self.stt_service,
                tts_service=self.tts_service,
                llm_service=self.llm_service,
                event_callback=event_callback,
            )
            
            print("[Container] ✅ All services initialized successfully")
        except Exception as e:
            print(f"[Container] ❌ INITIALIZATION FAILED: {e}")
            import traceback
            traceback.print_exc()
            raise