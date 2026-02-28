from domain.interfaces.IRepositories import IWorldStateRepository
from domain.interfaces.IServices import ISTTService, ITTSService, ILLMService

class ConversationManager:
    """
    Application Layer Manager orchestrating the conversation loop.
    Contains no framework-specific logic (no HTTP/FastAPI imports).
    """
    def __init__(
        self, 
        world_state_repo: IWorldStateRepository,
        stt_service: ISTTService,
        tts_service: ITTSService,
        llm_service: ILLMService
    ):
        self.world_state_repo = world_state_repo
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.llm_service = llm_service
        
    async def handle_utterance(self, player_id: str, audio_bytes: bytes) -> bytes:
        # Example flow combining services:
        text = await self.stt_service.transcribe(audio_bytes)
        state = await self.world_state_repo.get_player_state(player_id)
        reply_text = await self.llm_service.generate_response(text, state)
        reply_audio = await self.tts_service.synthesize(reply_text)
        return reply_audio
