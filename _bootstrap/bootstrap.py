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
    """
    Dependency Injection Container
    
    Initializes and wires all application dependencies.
    No framework-specific code - pure Python.
    """
    
    def __init__(self):
        # self.user_repo: IUserRepository = UserRepo()
        # self.oauth_credentials_repo: IOAuthCredentialsRepository = OAuthCredentialsRepo()
        pass
