
import redis.asyncio as aioredis
import os

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    print("REDISISHEREBITCH::: "+os.environ.get("REDIS_URL"))
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            os.environ.get("REDIS_URL"),
            encoding="utf-8",   
            decode_responses=True,
        )
    return _redis_client
