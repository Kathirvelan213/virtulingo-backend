"""
Events router — Unity game event ingest.

Unity client publishes world state change events via this endpoint.
The WorldStateManager dispatches them to the appropriate Redis state updates.

This is a lightweight HTTP endpoint for non-latency-critical game events.
For high-frequency position updates, consider upgrading to a WebSocket in future.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict

from api.dependency import WorldStateManagerDep

router = APIRouter()


class GameEvent(BaseModel):
    player_id: str
    event_type: str   # e.g., "PlayerPickedObject", "SceneChanged"
    payload: Dict[str, Any] = {}


@router.post("/")
async def ingest_event(event: GameEvent, world_state_manager: WorldStateManagerDep):
    """
    Ingest a game event from Unity and update the Redis world state.

    Supported event types:
      - PlayerMoved(x, y, z)
      - PlayerPickedObject(object_id)
      - PlayerDroppedObject(object_id)
      - PlayerEnteredProximity(npc_id)
      - PlayerLeftProximity(npc_id)
      - SceneChanged(scene_id)
      - DialogueStarted(npc_id)
      - DialogueEnded(npc_id)
    """
    await world_state_manager.handle_event(
        player_id=event.player_id,
        event_type=event.event_type,
        payload=event.payload,
    )
    return {"status": "ok", "event": event.event_type}


@router.get("/{player_id}/state")
async def get_player_state(player_id: str, world_state_manager: WorldStateManagerDep):
    """Return the current world state for a player (for debugging / UI overlay)."""
    return await world_state_manager.get_player_state(player_id)
