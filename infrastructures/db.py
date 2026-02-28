"""
Async database client pools for Supabase (PostgreSQL) and Redis.

Supabase connection notes:
  - Use the "Transaction" pooler URL (port 6543) for async/serverless workloads.
  - SSL is mandatory on Supabase — asyncpg requires ssl='require'.
  - Prepared statements must be disabled when using PgBouncer in transaction mode.
  - Find your connection string at: Supabase Dashboard → Project Settings → Database → Connection String
"""
import os

import asyncpg
import redis.asyncio as aioredis


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

_pg_pool: asyncpg.Pool | None = None


async def get_postgres_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            dsn=os.environ["SUPABASE_DB_URL"],
            min_size=2,
            max_size=10,
            command_timeout=10,
            ssl="require",                    # Supabase mandates SSL
            statement_cache_size=0,           # Required for PgBouncer transaction pooler
        )
    return _pg_pool


async def close_postgres_pool():
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            os.environ["REDIS_URL"],
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client
