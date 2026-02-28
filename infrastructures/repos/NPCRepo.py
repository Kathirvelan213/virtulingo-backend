"""
PostgreSQL-backed implementation of INPCRepository.

NPC base profiles are stored in Postgres. Relationship scores are stored
in Redis for fast updates during sessions, and periodically persisted.

Table: npcs
  npc_id              TEXT PRIMARY KEY
  name                TEXT NOT NULL
  personality         TEXT NOT NULL
  backstory           TEXT NOT NULL
  language_complexity TEXT NOT NULL   -- CEFR level
  emotional_tone      TEXT NOT NULL
  voice_id            TEXT NOT NULL

Table: npc_relationships
  npc_id     TEXT REFERENCES npcs(npc_id)
  player_id  TEXT NOT NULL
  score      FLOAT DEFAULT 0.0
  PRIMARY KEY (npc_id, player_id)
"""
from typing import Any, Dict

from domain.interfaces.IRepositories import INPCRepository
from infrastructures.db import get_postgres_pool


class PostgresNPCRepository(INPCRepository):
    async def _pool(self):
        return await get_postgres_pool()

    async def get_npc_profile(self, npc_id: str) -> Dict[str, Any]:
        pool = await self._pool()
        row = await pool.fetchrow(
            "SELECT * FROM npcs WHERE npc_id = $1", npc_id
        )
        if not row:
            raise ValueError(f"NPC '{npc_id}' not found in database.")
        return dict(row)

    async def update_relationship_score(
        self, npc_id: str, player_id: str, delta: float
    ) -> None:
        pool = await self._pool()
        await pool.execute(
            """
            INSERT INTO npc_relationships (npc_id, player_id, score)
            VALUES ($1, $2, $3)
            ON CONFLICT (npc_id, player_id)
            DO UPDATE SET score = LEAST(1.0, GREATEST(-1.0, npc_relationships.score + $3))
            """,
            npc_id, player_id, delta,
        )
