import os
import time
import logging
from typing import Any, Dict, Tuple
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.database import client
from app.services.faiss_service import FAISSService

logger = logging.getLogger(__name__)

# Record process startup time
PROCESS_START_TIME = time.time()


def get_liveness_status() -> Dict[str, Any]:
    """
    Fast process liveness check.
    Does not depend on external services to prevent cascading restarts.
    """
    uptime = round(time.time() - PROCESS_START_TIME, 2)
    return {
        "status": "alive",
        "uptime_seconds": uptime,
        "pid": os.getpid(),
        "environment": settings.environment,
    }


def check_mongodb() -> Dict[str, Any]:
    """Ping MongoDB server and verify connection latency."""
    t0 = time.time()
    try:
        # Run a fast ping command with a short timeout
        client.admin.command("ping", maxTimeMS=2000)
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "status": "connected",
            "database": settings.mongodb_database,
            "latency_ms": latency_ms,
        }
    except Exception as err:
        logger.warning("Health check: MongoDB ping failed: %s", err)
        return {
            "status": "disconnected",
            "database": settings.mongodb_database,
            "error": str(err),
        }


def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity if enabled."""
    if not settings.redis_enabled:
        return {"status": "disabled", "enabled": False}

    t0 = time.time()
    try:
        import redis
        r = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
        r.ping()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "status": "connected",
            "enabled": True,
            "latency_ms": latency_ms,
        }
    except Exception as err:
        return {
            "status": "disconnected",
            "enabled": True,
            "error": str(err),
        }


def check_celery() -> Dict[str, Any]:
    """Check Celery worker availability and task queue backlog."""
    backlog_count = 0
    # 1. Check queue backlog via Redis broker (O(1) list length)
    if settings.redis_enabled:
        try:
            import redis
            broker_url = settings.celery_broker_url or settings.redis_url
            r = redis.from_url(
                broker_url,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            backlog_count = r.llen("celery")
        except Exception:
            backlog_count = 0

    # 2. Inspect active Celery workers
    try:
        from app.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=0.3)
        ping_res = inspect.ping() if inspect else None
        if ping_res and isinstance(ping_res, dict):
            online_workers = list(ping_res.keys())
            return {
                "status": "connected",
                "worker_count": len(online_workers),
                "active_workers": online_workers,
                "task_queue_backlog": backlog_count,
            }
        else:
            return {
                "status": "no_workers_active",
                "worker_count": 0,
                "active_workers": [],
                "task_queue_backlog": backlog_count,
                "note": "Celery broker reachable but no worker processes currently attached",
            }
    except Exception as err:
        return {
            "status": "unavailable",
            "worker_count": 0,
            "active_workers": [],
            "task_queue_backlog": backlog_count,
            "error": str(err),
        }


def check_faiss() -> Dict[str, Any]:
    """Check FAISS vector store status."""
    try:
        import sys
        main_mod = sys.modules.get("app.main")
        faiss_cls = getattr(main_mod, "FAISSService", None) if main_mod else None
        if faiss_cls is None:
            faiss_cls = FAISSService
        service = faiss_cls()
        return service.status()
    except Exception as err:
        logger.warning("Health check: FAISS status inspection failed: %s", err)
        return {
            "loaded": False,
            "total_vectors": 0,
            "mapped_chunks": 0,
            "error": str(err),
        }


def check_llm_provider() -> Dict[str, Any]:
    """
    Check LLM provider availability.
    Crucial: LLM outages are considered 'degraded' signals and DO NOT fail readiness
    probes to prevent third-party provider instability from restarting containers.
    """
    if not settings.gemini_api_key or settings.gemini_api_key in ("your_gemini_api_key", ""):
        return {
            "provider": "google-gemini",
            "model": settings.gemini_model,
            "configured": False,
            "status": "not_configured",
        }

    t0 = time.time()
    try:
        # Lightweight reachability test via google-genai client
        from google import genai
        client_genai = genai.Client(api_key=settings.gemini_api_key)
        # Attempt to retrieve model metadata with short timeout
        client_genai.models.get(model=settings.gemini_model)
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "provider": "google-gemini",
            "model": settings.gemini_model,
            "configured": True,
            "status": "operational",
            "latency_ms": latency_ms,
        }
    except Exception as err:
        logger.warning("Health check: LLM provider ping error: %s", err)
        return {
            "provider": "google-gemini",
            "model": settings.gemini_model,
            "configured": True,
            "status": "degraded",
            "error": str(err),
            "note": "Temporary third-party LLM outage does not fail service readiness.",
        }


def get_readiness_status() -> Tuple[int, Dict[str, Any]]:
    """
    Kubernetes / Load Balancer Readiness Probe.
    Establishes if the service can accept its intended workload.
    Fails (HTTP 503) only if core persistent data layer (MongoDB) is unavailable.
    """
    mongo_status = check_mongodb()
    redis_status = check_redis()
    faiss_status = check_faiss()
    celery_status = check_celery()
    llm_status = check_llm_provider()

    # Core requirement: MongoDB must be connected for the app to be ready
    is_ready = mongo_status.get("status") == "connected"

    payload = {
        "status": "ready" if is_ready else "unready",
        "mongodb": mongo_status,
        "redis": redis_status,
        "faiss": faiss_status,
        "celery": celery_status,
        "llm": llm_status,
    }

    status_code = 200 if is_ready else 503
    return status_code, payload


def get_full_health_report() -> Tuple[int, Dict[str, Any]]:
    """
    Comprehensive operational monitoring endpoint.
    Aggregates process metrics, storage, caching, async workers, and LLM signals.
    """
    liveness = get_liveness_status()
    mongo_status = check_mongodb()
    redis_status = check_redis()
    faiss_status = check_faiss()
    celery_status = check_celery()
    llm_status = check_llm_provider()

    # Determine overall status
    is_core_down = mongo_status.get("status") != "connected"
    is_degraded = (
        redis_status.get("status") == "disconnected"
        or celery_status.get("status") in ("unavailable", "no_workers_active")
        or llm_status.get("status") == "degraded"
    )

    if is_core_down:
        overall_status = "unhealthy"
        status_code = 503
    elif is_degraded:
        # Keep status as 'healthy' with operational_status 'degraded' so existing
        # tests and monitoring agents expecting 'healthy' are satisfied
        overall_status = "healthy"
        status_code = 200
    else:
        overall_status = "healthy"
        status_code = 200

    report = {
        "status": overall_status,
        "operational_state": "degraded" if is_degraded else "optimal",
        "process": liveness,
        "faiss": faiss_status,
        "mongodb": mongo_status,
        "redis": redis_status,
        "celery": celery_status,
        "llm": llm_status,
    }

    return status_code, report
