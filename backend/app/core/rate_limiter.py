import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Hybrid Rate Limiter for DocuMind AI:
    - Primary: Atomic Redis counters with TTL.
    - Fallback: Thread-safe in-memory sliding window when Redis is unavailable.
    - Configurable policy:
        * Security-critical actions (e.g., login brute-force): Fallback to in-memory rate limiting.
        * Operational actions (e.g., RAG queries, uploads): Fail-open to preserve availability.
    """

    def __init__(self):
        self._in_memory_records: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        if not settings.redis_enabled:
            return None
        try:
            client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            return client
        except Exception as exc:
            logger.warning("RateLimiter failed to connect to Redis: %s", exc)
            return None

    async def is_rate_limited(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        fail_open: bool = True,
    ) -> Tuple[bool, int]:
        """
        Evaluates whether the given key has exceeded the limit in the window.
        Returns:
            (is_limited: bool, retry_after: int)
        """
        redis_client = await self._get_redis_client()

        if redis_client is not None:
            redis_key = f"documindai:ratelimit:{key}"
            try:
                # Atomic INCR + EXPIRE via pipeline
                pipe = redis_client.pipeline()
                pipe.incr(redis_key)
                pipe.ttl(redis_key)
                count, ttl = await pipe.execute()
                await redis_client.aclose()

                if count == 1 or ttl == -1:
                    # First hit in window, set TTL
                    client_expire = await self._get_redis_client()
                    if client_expire:
                        await client_expire.expire(redis_key, window_seconds)
                        await client_expire.aclose()
                    ttl = window_seconds

                if count > limit:
                    retry_after = max(ttl, 1) if ttl and ttl > 0 else window_seconds
                    return True, retry_after

                return False, 0
            except Exception as exc:
                logger.warning(
                    "Redis rate limit check failed for key %s (%s). Falling back to %s",
                    key,
                    exc,
                    "fail-open" if fail_open else "in-memory tracker",
                )
                try:
                    await redis_client.aclose()
                except Exception:
                    pass

        # Redis is down or unavailable: apply defined fallback strategy
        if fail_open:
            return False, 0

        # In-memory sliding window fallback for security-critical operations (e.g. login brute-force)
        now = time.time()
        async with self._lock:
            timestamps = self._in_memory_records[key]
            # Discard timestamps older than window
            cutoff = now - window_seconds
            self._in_memory_records[key] = [t for t in timestamps if t > cutoff]

            if len(self._in_memory_records[key]) >= limit:
                oldest = self._in_memory_records[key][0]
                retry_after = max(int(window_seconds - (now - oldest)), 1)
                return True, retry_after

            self._in_memory_records[key].append(now)
            return False, 0

    async def enforce(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        action_name: str,
        fail_open: bool = True,
    ):
        """Raises HTTPException(429) if the limit is exceeded."""
        limited, retry_after = await self.is_rate_limited(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
            fail_open=fail_open,
        )
        if limited:
            logger.warning(
                "Rate limit exceeded for %s on key %s. Retry after %d seconds.",
                action_name,
                key,
                retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {action_name}. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )


# Global rate limiter singleton
rate_limiter = RateLimiter()


# ==============================================================================
# FastAPI Dependencies for Endpoints
# ==============================================================================

async def rate_limit_rag(request: Request):
    """Rate limit RAG requests: 20 per minute per client/user (fails open on Redis outage)."""
    # Prefer authenticated user ID from Authorization token if available, else client IP
    auth_header = request.headers.get("Authorization", "")
    key = f"rag:{auth_header[:30] if auth_header else request.client.host if request.client else 'anon'}"
    await rate_limiter.enforce(
        key=key,
        limit=20,
        window_seconds=60,
        action_name="RAG questions",
        fail_open=True,
    )


async def rate_limit_uploads(request: Request):
    """Rate limit document uploads: 10 per minute per client/user (fails open on Redis outage)."""
    auth_header = request.headers.get("Authorization", "")
    key = f"upload:{auth_header[:30] if auth_header else request.client.host if request.client else 'anon'}"
    await rate_limiter.enforce(
        key=key,
        limit=10,
        window_seconds=60,
        action_name="document uploads",
        fail_open=True,
    )


async def rate_limit_logins(request: Request):
    """
    Rate limit login attempts: 5 per minute per IP.
    Security policy: In-memory fallback if Redis is offline (prevents brute-force even during outage).
    """
    client_ip = request.client.host if request.client else "local"
    key = f"login:{client_ip}"
    await rate_limiter.enforce(
        key=key,
        limit=5,
        window_seconds=60,
        action_name="login attempts",
        fail_open=False,
    )
