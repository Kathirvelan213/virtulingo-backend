"""
Dependency Injection Container and Bootstrap
"""
from fastapi import FastAPI
from application.ConversationManager import ConversationManager
from application.GrammarManager import GrammarManager

# In reality, import the concrete implementations here
# from infrastructure.repositories.RedisWorldStateRepository import RedisWorldStateRepository
# from infrastructure.services.DeepgramSTTService import DeepgramSTTService

class Container:
    def __init__(self):
        # Repositories (Instantiate concrete classes)
        self.world_state_repo = None # e.g., RedisWorldStateRepository()
        self.mistake_repo = None
        self.player_profile_repo = None
        
        # Services (Instantiate concrete classes)
        self.stt_service = None # e.g., DeepgramSTTService()
        self.tts_service = None
        self.llm_service = None
        
        # Managers: Inject implementations directly into the orchestrators
        self.conversation_manager = ConversationManager(
            world_state_repo=self.world_state_repo,
            stt_service=self.stt_service,
            tts_service=self.tts_service,
            llm_service=self.llm_service
        )
        self.grammar_manager = GrammarManager()

def bootstrap_app(app: FastAPI):
    """
    Initializes the dependency injection container and attaches it to the app state.
    """
    app.state.container = Container()
