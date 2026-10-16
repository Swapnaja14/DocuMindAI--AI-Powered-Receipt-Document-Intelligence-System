import asyncio
import hashlib
import json
import logging
import os
from typing import Any
from dotenv import load_dotenv

from redis.asyncio import Redis
from redis.exceptions import RedisError

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

CACHE_TTL_SECONDS = int(
    os.getenv("REDIS_CACHE_TTL_SECONDS", "600")
)

REDIS_ENABLED = (
    os.getenv("REDIS_ENABLED", "true").lower() == "true"
)

_redis: Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


async def get_redis() -> Redis | None:
    """Return the shared Redis client, if caching is enabled."""
    global _redis, _redis_loop

    if not REDIS_ENABLED:
        return None

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    # Reset client if attached to a closed or obsolete event loop (e.g. across TestClient calls)
    if _redis is not None and (_redis_loop is None or _redis_loop.is_closed() or _redis_loop != current_loop):
        _redis = None
        _redis_loop = None

    if _redis is None:
        # Avoid Windows IPv6 resolution latency for localhost
        resolved_url = REDIS_URL.replace("://localhost:", "://127.0.0.1:") if "://localhost:" in REDIS_URL else REDIS_URL
        _redis = Redis.from_url(
            resolved_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        _redis_loop = current_loop

    return _redis


def make_cache_key(
    user_id: str,
    query: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Build a stable, user-isolated cache key."""
    payload = {
        "user_id": str(user_id),
        "query": " ".join(query.casefold().split()),
        "context": context or {},
        "version": 1,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return f"documindai:rag:v1:user:{user_id}:{digest}"


async def get_cached_answer(
    key: str,
) -> dict[str, Any] | None:
    """Return a cached JSON object, or None on a miss."""
    try:
        client = await get_redis()
        if client is None:
            return None

        value = await client.get(key)

        if value is None:
            return None

        result = json.loads(value)

        if not isinstance(result, dict):
            logger.warning("Invalid cached response format")
            return None

        return result

    except Exception:
        logger.warning(
            "Redis cache read failed",
            exc_info=True,
        )
        return None


async def cache_answer(
    key: str,
    answer: dict[str, Any],
    ttl: int = CACHE_TTL_SECONDS,
) -> None:
    """Cache a successful JSON-serializable response."""
    try:
        client = await get_redis()
        if client is None:
            return

        value = json.dumps(
            answer,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        await client.set(key, value, ex=ttl)

    except Exception:
        logger.warning(
            "Redis cache write failed",
            exc_info=True,
        )


async def invalidate_user_cache(
    user_id: str,
) -> int:
    """Delete cached RAG answers belonging to one user."""
    try:
        client = await get_redis()
        if client is None:
            return 0

        pattern = f"documindai:rag:v1:user:{user_id}:*"
        deleted = 0

        async for key in client.scan_iter(
            match=pattern,
            count=200,
        ):
            deleted += await client.delete(key)

        return deleted

    except Exception as exc:
        logger.error(
            "Redis cache invalidation failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0


def invalidate_user_cache_sync(
    user_id: str,
) -> int:
    """Synchronously delete cached RAG answers belonging to one user (for Celery workers)."""
    if not REDIS_ENABLED:
        return 0

    try:
        import redis as sync_redis

        resolved_url = (
            REDIS_URL.replace("://localhost:", "://127.0.0.1:")
            if "://localhost:" in REDIS_URL
            else REDIS_URL
        )
        client = sync_redis.Redis.from_url(
            resolved_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        pattern = f"documindai:rag:v1:user:{user_id}:*"
        deleted = 0

        for key in client.scan_iter(match=pattern, count=200):
            deleted += client.delete(key)

        return deleted

    except Exception as exc:
        logger.error(
            "Synchronous Redis cache invalidation failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0

