"""
FastAPI Dependency Injection Providers

This module provides dependency injection functions for FastAPI routes.
All dependencies are stored in app.state.container and injected via Depends().
API routers MUST only import from this file — never directly from application or infrastructure.
"""
from fastapi import Depends
from typing import Annotated, Callable

from application.ConversationManager import ConversationManager
from application.GrammarManager import GrammarManager
from application.WorldStateManager import WorldStateManager
from application.ReviewScheduler import ReviewScheduler
from application.DialogueOrchestrator import DialogueOrchestrator
from domain.interfaces.IRepositories import (
    IWorldStateRepository,
    IMistakeRepository,
    INPCRepository,
)


def from_container(attr: str) -> Callable:
    """
    Factory function to extract an attribute from app.state.container.
    Works with both HTTP (Request) and WebSocket endpoints.
    FastAPI automatically injects the appropriate type.
    """
    def dep(conn):
        # conn can be either Request or WebSocket
        # Both have .app.state attribute
        result = getattr(conn.app.state.container, attr)
        print(f"[Dependency] Injected {attr}")
        return result
    
    return dep


# ── Manager Dependencies ──────────────────────────────────────────────────────
ConversationManagerDep = Annotated[ConversationManager, Depends(from_container("conversation_manager"))]
GrammarManagerDep = Annotated[GrammarManager, Depends(from_container("grammar_manager"))]
WorldStateManagerDep = Annotated[WorldStateManager, Depends(from_container("world_state_manager"))]
ReviewSchedulerDep = Annotated[ReviewScheduler, Depends(from_container("review_scheduler"))]
DialogueOrchestratorDep = Annotated[DialogueOrchestrator, Depends(from_container("dialogue_orchestrator"))]

# ── Repository Dependencies ───────────────────────────────────────────────────
WorldStateRepoDep = Annotated[IWorldStateRepository, Depends(from_container("world_state_repo"))]
MistakeRepoDep = Annotated[IMistakeRepository, Depends(from_container("mistake_repo"))]
NPCRepoDep = Annotated[INPCRepository, Depends(from_container("npc_repo"))]
