import asyncio
import hashlib
import json
import logging
import os
from typing import Any
from dotenv import load_dotenv

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.services.cache_metrics import cache_metrics

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
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_loop = current_loop

    return _redis


def _normalize_context_value(val: Any) -> Any:
    """Recursively normalize dict keys and sort list items for stable cache key generation."""
    if isinstance(val, dict):
        return {k: _normalize_context_value(v) for k, v in sorted(val.items())}
    if isinstance(val, (list, tuple, set)):
        normalized_items = [_normalize_context_value(x) for x in val]
        try:
            return sorted(
                normalized_items,
                key=lambda x: json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x),
            )
        except Exception:
            return normalized_items
    return val


LUA_ATOMIC_CACHE_WRITE = """
local current = redis.call("GET", KEYS[1]) or "0"

if current ~= ARGV[1] then
    return 0
end

redis.call("SET", KEYS[2], ARGV[2], "EX", ARGV[3])
return 1
"""

LUA_RELEASE_LOCK = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


async def acquire_lock(lock_key: str, token: str, ttl: int = 15) -> bool:
    """Acquire a distributed lock with a unique token and short TTL."""
    try:
        client = await get_redis()
        if client is None:
            return False

        res = await client.set(lock_key, token, nx=True, ex=ttl)
        return bool(res)
    except Exception:
        logger.warning(
            "Redis acquire_lock failed for key %s",
            lock_key,
            exc_info=True,
        )
        return False


async def release_lock(lock_key: str, token: str) -> bool:
    """Safely release a distributed lock using atomic compare-and-delete Lua logic."""
    try:
        client = await get_redis()
        if client is None:
            return False

        res = await client.eval(LUA_RELEASE_LOCK, 1, lock_key, token)
        return bool(res == 1)
    except Exception:
        logger.warning(
            "Redis release_lock failed for key %s",
            lock_key,
            exc_info=True,
        )
        return False


async def wait_for_cached_answer(
    cache_key: str,
    lock_key: str,
    timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> dict[str, Any] | None:
    """
    Poll for a cached answer while another request holds the generation lock.
    Returns the cached answer if it becomes available before the timeout.
    """
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            await asyncio.sleep(poll_interval)
            cached = await get_cached_answer(cache_key)
            if cached is not None:
                return cached

            client = await get_redis()
            if client is not None:
                try:
                    if not await client.exists(lock_key):
                        return await get_cached_answer(cache_key)
                except Exception:
                    pass

        return None
    except Exception:
        logger.warning("Error waiting for cached answer", exc_info=True)
        return None


def make_generation_key(user_id: str) -> str:
    """Return the Redis key tracking the current cache generation for a user."""
    return f"documindai:rag:generation:{{{user_id}}}"


async def get_user_generation(user_id: str) -> int:
    """Read the user's current cache generation counter."""
    try:
        client = await get_redis()
        if client is None:
            return 0

        gen_val = await client.get(make_generation_key(user_id))
        return int(gen_val) if gen_val is not None else 0
    except Exception:
        logger.warning(
            "Redis get_user_generation failed for user %s",
            user_id,
            exc_info=True,
        )
        return 0


def get_user_generation_sync(user_id: str) -> int:
    """Synchronously read the user's current cache generation counter."""
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
        gen_val = client.get(make_generation_key(user_id))
        return int(gen_val) if gen_val is not None else 0
    except Exception:
        logger.warning(
            "Synchronous Redis get_user_generation failed for user %s",
            user_id,
            exc_info=True,
        )
        return 0


async def increment_user_generation(user_id: str) -> int:
    """Increment the generation counter for a user when their documents mutate."""
    try:
        client = await get_redis()
        if client is None:
            return 0

        new_gen = await client.incr(make_generation_key(user_id))
        return int(new_gen)
    except Exception as exc:
        logger.error(
            "Redis increment_user_generation failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0


def increment_user_generation_sync(user_id: str) -> int:
    """Synchronously increment the generation counter for a user."""
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
        new_gen = client.incr(make_generation_key(user_id))
        return int(new_gen)
    except Exception as exc:
        logger.error(
            "Synchronous Redis increment_user_generation failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0


def make_cache_key(
    user_id: str,
    query: str,
    context: dict[str, Any] | None = None,
    generation: int | str | None = None,
) -> str:
    """Build a stable, user-isolated cache key incorporating user generation if specified."""
    normalized_context = _normalize_context_value(context) if context else {}
    payload = {
        "user_id": str(user_id),
        "query": " ".join(query.casefold().split()),
        "context": normalized_context,
        "version": 1,
    }
    if generation is not None:
        payload["generation"] = str(generation)

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if generation is not None:
        return f"documindai:rag:v1:user:{{{user_id}}}:gen:{generation}:{digest}"
    return f"documindai:rag:v1:user:{{{user_id}}}:{digest}"


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
            cache_metrics.record_invalid_entry()
            return None

        return result

    except Exception as exc:
        logger.warning(
            "Redis cache read failed",
            exc_info=True,
        )
        cache_metrics.record_read_error(exc)
        return None


async def cache_answer(
    key: str,
    answer: dict[str, Any],
    ttl: int = CACHE_TTL_SECONDS,
    user_id: str | None = None,
    expected_generation: int | str | None = None,
) -> bool:
    """Cache a successful JSON-serializable response atomically with generation check."""
    try:
        client = await get_redis()
        if client is None:
            return False

        value = json.dumps(
            answer,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        # Auto-extract user_id and expected_generation from key if omitted
        if user_id is None or expected_generation is None:
            try:
                parts = key.split(":")
                if len(parts) >= 8 and parts[3] == "user" and parts[5] == "gen":
                    extracted_user = parts[4].strip("{}")
                    extracted_gen = parts[6]
                    if user_id is None:
                        user_id = extracted_user
                    if expected_generation is None:
                        expected_generation = extracted_gen
            except Exception:
                pass

        if user_id is not None and expected_generation is not None:
            gen_key = make_generation_key(user_id)
            res = await client.eval(
                LUA_ATOMIC_CACHE_WRITE,
                2,
                gen_key,
                key,
                str(expected_generation),
                value,
                str(ttl),
            )
            return bool(res == 1)

        await client.set(key, value, ex=ttl)
        return True

    except Exception as exc:
        logger.warning(
            "Redis cache write failed",
            exc_info=True,
        )
        cache_metrics.record_write_error(exc)
        return False


async def invalidate_user_cache(
    user_id: str,
) -> int:
    """Delete cached RAG answers and increment generation counter for one user."""
    try:
        client = await get_redis()
        if client is None:
            return 0

        # Increment generation counter to reject in-flight stale writes
        await client.incr(make_generation_key(user_id))

        deleted = 0
        patterns = [
            f"documindai:rag:v1:user:{{{user_id}}}:*",
            f"documindai:rag:v1:user:{user_id}:*",
        ]

        for pattern in patterns:
            async for key in client.scan_iter(
                match=pattern,
                count=200,
            ):
                deleted += await client.delete(key)

        cache_metrics.record_invalidation(deleted if deleted > 0 else 1)
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
    """Synchronously delete cached RAG answers and increment generation counter for one user."""
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

        # Increment generation counter
        client.incr(make_generation_key(user_id))

        deleted = 0
        patterns = [
            f"documindai:rag:v1:user:{{{user_id}}}:*",
            f"documindai:rag:v1:user:{user_id}:*",
        ]

        for pattern in patterns:
            for key in client.scan_iter(match=pattern, count=200):
                deleted += client.delete(key)

        cache_metrics.record_invalidation(deleted if deleted > 0 else 1)
        return deleted

    except Exception as exc:
        logger.error(
            "Synchronous Redis cache invalidation failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0

