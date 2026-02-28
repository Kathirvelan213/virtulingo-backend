"""
PostgreSQL-backed implementation of IMistakeRepository.

Persists grammar mistakes and exposes aggregation queries for the review scheduler.

Table: grammar_mistakes
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
  player_id   TEXT NOT NULL
  category    TEXT NOT NULL          -- e.g., "verb_conjugation"
  original    TEXT NOT NULL
  correction  TEXT NOT NULL
  explanation TEXT NOT NULL
  severity    INTEGER DEFAULT 1
  created_at  TIMESTAMPTZ DEFAULT now()
"""
from typing import Any, Dict, List

from domain.interfaces.IRepositories import IMistakeRepository
from infrastructures.db import get_postgres_pool


class PostgresMistakeRepository(IMistakeRepository):
    async def _pool(self):
        return await get_postgres_pool()

    async def log_mistake(
        self,
        player_id: str,
        category: str,
        original: str,
        correction: str,
        explanation: str,
        severity: int = 1,
    ) -> None:
        pool = await self._pool()
        await pool.execute(
            """
            INSERT INTO grammar_mistakes (player_id, category, original, correction, explanation, severity)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            player_id, category, original, correction, explanation, severity,
        )

    async def get_top_mistakes(
        self, player_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        pool = await self._pool()
        rows = await pool.fetch(
            """
            SELECT category, COUNT(*) AS count
            FROM grammar_mistakes
            WHERE player_id = $1
            GROUP BY category
            ORDER BY count DESC
            LIMIT $2
            """,
            player_id, limit,
        )
        return [dict(row) for row in rows]

    async def get_recent_mistakes(
        self, player_id: str, since_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        pool = await self._pool()
        rows = await pool.fetch(
            """
            SELECT id, category, original, correction, explanation, created_at
            FROM grammar_mistakes
            WHERE player_id = $1
              AND created_at >= now() - ($2 || ' minutes')::interval
            ORDER BY created_at DESC
            """,
            player_id, str(since_minutes),
        )
        return [dict(row) for row in rows]
    
    async def log_mistake(
        self, player_id: str, category: str, original: str, correction: str, explanation: str
    ) -> None:
        await self.log_mistake(player_id, category, original, correction, explanation, severity=1)
