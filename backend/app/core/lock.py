from contextlib import contextmanager
import threading
from typing import Optional
import redis

from app.core.config import settings

_redis_client: Optional[redis.Redis] = None
_local_process_lock = threading.Lock()


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            client = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = None
    return _redis_client


@contextmanager
def faiss_lock(
    name: str = "lock:faiss_index_write",
    timeout: int = 30,
    blocking_timeout: int = 15,
):
    """
    Acquires a Redis distributed lock to serialize atomic FAISS index updates
    across concurrent Celery worker processes.

    If Redis is unreachable (e.g. local offline unit test mode), it gracefully
    falls back to an in-process thread lock.
    """
    client = get_redis_client()
    if client is not None:
        try:
            lock = client.lock(
                name=name,
                timeout=timeout,
                blocking_timeout=blocking_timeout,
            )
            acquired = lock.acquire(blocking=True)
            if not acquired:
                raise TimeoutError(
                    f"Could not acquire FAISS lock '{name}' within {blocking_timeout}s"
                )
            try:
                yield
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
            return
        except (redis.ConnectionError, redis.TimeoutError):
            pass

    # Thread-safe fallback for local test execution
    with _local_process_lock:
        yield
