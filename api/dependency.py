"""
FastAPI Dependency Injection Providers

This module provides dependency injection functions for FastAPI routes.
All dependencies are stored in app.state.container and injected via Depends().
"""
from fastapi import Depends, Request
from typing import Annotated, Callable

from application.ConversationManager import ConversationManager
from application.GrammarManager import GrammarManager
from domain.interfaces.IRepositories import (
    IWorldStateRepository,
    IMistakeRepository,
    IPlayerProfileRepository
)
from domain.interfaces.IServices import (
    ISTTService,
    ITTSService,
    ILLMService
)


def from_container(attr: str) -> Callable:
    """
    Factory function to create a dependency that extracts an attribute from the container.

    Args:
        attr: Name of the attribute in app.state.container

    Returns:
        Dependency function that retrieves the attribute
    """
    def dep(request: Request):
        return getattr(request.app.state.container, attr)
    return dep


# Reusable Dependency Type Aliases
ConversationManagerDep = Annotated[ConversationManager, Depends(from_container("conversation_manager"))]
GrammarManagerDep = Annotated[GrammarManager, Depends(from_container("grammar_manager"))]

WorldStateRepoDep = Annotated[IWorldStateRepository, Depends(from_container("world_state_repo"))]
MistakeRepoDep = Annotated[IMistakeRepository, Depends(from_container("mistake_repo"))]
PlayerProfileRepoDep = Annotated[IPlayerProfileRepository, Depends(from_container("player_profile_repo"))]

STTServiceDep = Annotated[ISTTService, Depends(from_container("stt_service"))]
TTSServiceDep = Annotated[ITTSService, Depends(from_container("tts_service"))]
LLMServiceDep = Annotated[ILLMService, Depends(from_container("llm_service"))]
