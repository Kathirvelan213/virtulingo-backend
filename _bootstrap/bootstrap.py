"""
Dependency Injection Container

Pure dependency wiring with no FastAPI dependencies.
All application dependencies are initialized here.
"""
# from domain.interfaces.IRepositories import (
#     IUserRepository,
#     IOAuthCredentialsRepository,
#     IEmailRepository,
#     IEmailVectorRepository,
#     ISummaryRepository,
#     IDraftRepository,
#     IEventRepository,
#     ISyncStateRepository
# )
# from infrastructure.GoogleAuthService import GoogleAuthService
# from infrastructure.repos.UserRepo import UserRepo
# from infrastructure.repos.OAuthCredentialsRepo import OAuthCredentialsRepo
# from infrastructure.repos.EmailRepo import EmailRepository
# from infrastructure.repos.EmailVectorRepo import EmailVectorRepository
# from infrastructure.repos.SummaryRepo import SummaryRepository
# from infrastructure.repos.DraftRepo import DraftRepository
# from infrastructure.repos.EventRepo import EventRepository
# from infrastructure.repos.SyncStateRepo import SyncStateRepository
# from application.AuthManager import AuthManager



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
        
container=Container()