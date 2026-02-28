"""
Redis-backed implementation of IWorldStateRepository.

Player world state (position, nearby NPCs, held objects, scene, conversation history)
is stored in Redis hashes and lists for O(1) reads during LLM prompt assembly.

Key schema:
  player:state:{player_id}     → Redis HASH (player world state fields)
  player:conv:{player_id}:{npc_id} → Redis LIST (capped conversation history)
"""
import json
from typing import Any, Dict, List

from domain.interfaces.IRepositories import IWorldStateRepository
from infrastructures.db import get_redis_client

_STATE_TTL_SECONDS = 3600        # 1-hour session TTL
_CONVERSATION_MAX_TURNS = 20     # Keep at most 20 turns per NPC in memory


class RedisWorldStateRepository(IWorldStateRepository):
    def __init__(self):
        self._redis = get_redis_client()

    def _state_key(self, player_id: str) -> str:
        return f"player:state:{player_id}"

    def _conv_key(self, player_id: str, npc_id: str) -> str:
        return f"player:conv:{player_id}:{npc_id}"

    async def get_player_state(self, player_id: str) -> Dict[str, Any]:
        raw = await self._redis.hgetall(self._state_key(player_id))
        if not raw:
            # Return sensible defaults for a new player
            return {
                "player_id": player_id,
                "language": "fr",
                "proficiency_level": "A2",
                "scene_id": "marketplace",
                "object_in_hand": None,
                "nearby_npcs": [],
                "active_quest": None,
                "active_npc_id": None,
            }
        # Deserialize JSON-encoded list fields
        for field_name in ("nearby_npcs",):
            if field_name in raw:
                raw[field_name] = json.loads(raw[field_name])
        return raw

    async def update_player_state(self, player_id: str, patch: Dict[str, Any]) -> None:
        key = self._state_key(player_id)
        # Encode list values as JSON strings for Redis HASH storage
        serialized = {}
        for k, v in patch.items():
            if isinstance(v, (list, dict)):
                serialized[k] = json.dumps(v)
            elif v is None:
                serialized[k] = ""
            else:
                serialized[k] = str(v)

        async with self._redis.pipeline(transaction=True) as pipe:
            await pipe.hset(key, mapping=serialized)
            await pipe.expire(key, _STATE_TTL_SECONDS)
            await pipe.execute()

    async def get_conversation_history(
        self, player_id: str, npc_id: str, window: int = 10
    ) -> List[Dict[str, str]]:
        key = self._conv_key(player_id, npc_id)
        # Fetch the last `window` turns (right end of list = newest)
        raw_turns = await self._redis.lrange(key, -window, -1)
        return [json.loads(turn) for turn in raw_turns]

    async def append_conversation_turn(
        self, player_id: str, npc_id: str, role: str, content: str
    ) -> None:
        key = self._conv_key(player_id, npc_id)
        turn = json.dumps({"role": role, "content": content})
        async with self._redis.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, turn)
            # Cap the list to avoid unbounded memory growth
            await pipe.ltrim(key, -_CONVERSATION_MAX_TURNS, -1)
            await pipe.expire(key, _STATE_TTL_SECONDS)
            await pipe.execute()
