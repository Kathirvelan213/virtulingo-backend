"""
Dependency Injection Container — bootstrap wiring of all concrete implementations.

Pure Python, no FastAPI imports. All infrastructure is instantiated here
and wired into application-layer managers.
"""
from application.ConversationManager import ConversationManager
from application.GrammarManager import GrammarManager
from application.WorldStateManager import WorldStateManager
from application.ReviewScheduler import ReviewScheduler

from infrastructures.LLM import OllamaLLM
from infrastructures.SpeechToText import WhisperSTT
from infrastructures.TextToSpeech import CoquiTTS
from infrastructures.repos.WorldStateRepo import RedisWorldStateRepository
from infrastructures.repos.MistakeRepo import PostgresMistakeRepository
from infrastructures.repos.NPCRepo import PostgresNPCRepository


class Container:
    def __init__(self):
        # ── Infrastructure: AI services ──────────────────────────────
        self.llm_service = OllamaLLM()
        self.stt_service = WhisperSTT()
        self.tts_service = CoquiTTS()

        # ── Infrastructure: Repositories ─────────────────────────────
        self.world_state_repo = RedisWorldStateRepository()
        self.mistake_repo = PostgresMistakeRepository()
        self.npc_repo = PostgresNPCRepository()

        # ── Application: Managers (DI injected) ──────────────────────
        self.conversation_manager = ConversationManager(
            world_state_repo=self.world_state_repo,
            mistake_repo=self.mistake_repo,
            npc_repo=self.npc_repo,
            player_profile_repo=None,    # TODO: add PlayerProfileRepository
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