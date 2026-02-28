"""
WorldStateManager — handles all game events from Unity.

Unity publishes structured events (player moved, picked up object, etc.).
This manager processes them and updates the Redis world state store.

No LLM or TTS involved — this is pure state management.
"""
from typing import Any, Dict

from domain.interfaces.IRepositories import IWorldStateRepository


# Event type constants matching what Unity will send
EVENT_PLAYER_MOVED = "PlayerMoved"
EVENT_PLAYER_PICKED_OBJECT = "PlayerPickedObject"
EVENT_PLAYER_DROPPED_OBJECT = "PlayerDroppedObject"
EVENT_PLAYER_ENTERED_PROXIMITY = "PlayerEnteredProximity"
EVENT_PLAYER_LEFT_PROXIMITY = "PlayerLeftProximity"
EVENT_SCENE_CHANGED = "SceneChanged"
EVENT_DIALOGUE_STARTED = "DialogueStarted"
EVENT_DIALOGUE_ENDED = "DialogueEnded"


class WorldStateManager:
    def __init__(self, world_state_repo: IWorldStateRepository):
        self._state = world_state_repo

    async def handle_event(self, player_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Dispatch a Unity game event to the appropriate state update handler.
        """
        handlers = {
            EVENT_PLAYER_MOVED: self._on_player_moved,
            EVENT_PLAYER_PICKED_OBJECT: self._on_picked_object,
            EVENT_PLAYER_DROPPED_OBJECT: self._on_dropped_object,
            EVENT_PLAYER_ENTERED_PROXIMITY: self._on_entered_proximity,
            EVENT_PLAYER_LEFT_PROXIMITY: self._on_left_proximity,
            EVENT_SCENE_CHANGED: self._on_scene_changed,
            EVENT_DIALOGUE_STARTED: self._on_dialogue_started,
            EVENT_DIALOGUE_ENDED: self._on_dialogue_ended,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(player_id, payload)

    async def get_player_state(self, player_id: str) -> Dict[str, Any]:
        return await self._state.get_player_state(player_id)

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    async def _on_player_moved(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "position_x": payload.get("x", 0),
            "position_y": payload.get("y", 0),
            "position_z": payload.get("z", 0),
        })

    async def _on_picked_object(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "object_in_hand": payload.get("object_id"),
        })

    async def _on_dropped_object(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "object_in_hand": None,
        })

    async def _on_entered_proximity(self, player_id: str, payload: Dict) -> None:
        state = await self._state.get_player_state(player_id)
        nearby = state.get("nearby_npcs", [])
        npc_id = payload.get("npc_id")
        if npc_id and npc_id not in nearby:
            nearby.append(npc_id)
        await self._state.update_player_state(player_id, {"nearby_npcs": nearby})

    async def _on_left_proximity(self, player_id: str, payload: Dict) -> None:
        state = await self._state.get_player_state(player_id)
        nearby = state.get("nearby_npcs", [])
        npc_id = payload.get("npc_id")
        nearby = [n for n in nearby if n != npc_id]
        await self._state.update_player_state(player_id, {"nearby_npcs": nearby})

    async def _on_scene_changed(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "scene_id": payload.get("scene_id"),
            "nearby_npcs": [],          # Clear proximity on scene transition
            "object_in_hand": None,
        })

    async def _on_dialogue_started(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "active_npc_id": payload.get("npc_id"),
        })

    async def _on_dialogue_ended(self, player_id: str, payload: Dict) -> None:
        await self._state.update_player_state(player_id, {
            "active_npc_id": None,
        })
