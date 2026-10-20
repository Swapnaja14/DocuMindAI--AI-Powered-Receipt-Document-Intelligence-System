import os
import time
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.database import client, db
from app.core.telemetry import telemetry_collector
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
    """Ping MongoDB server, measure latency, and collect storage statistics."""
    t0 = time.time()
    try:
        client.admin.command("ping", maxTimeMS=2000)
        latency_ms = round((time.time() - t0) * 1000, 2)

        storage_stats = {
            "collections": 0,
            "objects": 0,
            "data_size_mb": 0.0,
            "storage_size_mb": 0.0,
        }
        try:
            raw_stats = db.command("dbStats")
            storage_stats = {
                "collections": raw_stats.get("collections", 0),
                "objects": raw_stats.get("objects", 0),
                "data_size_mb": round(raw_stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(raw_stats.get("storageSize", 0) / (1024 * 1024), 2),
            }
        except Exception:
            pass

        return {
            "status": "connected",
            "database": settings.mongodb_database,
            "latency_ms": latency_ms,
            "storage": storage_stats,
        }
    except Exception as err:
        logger.warning("Health check: MongoDB ping failed: %s", err)
        return {
            "status": "disconnected",
            "database": settings.mongodb_database,
            "error": str(err),
        }


def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity, memory footprint, cache hits, and eviction stats."""
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

        info_mem = {}
        info_stats = {}
        try:
            info_mem = r.info("memory")
            info_stats = r.info("stats")
        except Exception:
            pass

        hits = info_stats.get("keyspace_hits", 0)
        misses = info_stats.get("keyspace_misses", 0)
        total_lookups = hits + misses
        hit_rate = round(hits / total_lookups * 100, 2) if total_lookups > 0 else 0.0

        return {
            "status": "connected",
            "enabled": True,
            "latency_ms": latency_ms,
            "memory": {
                "used_memory_human": info_mem.get("used_memory_human", "unknown"),
                "maxmemory_human": info_mem.get("maxmemory_human", "unknown"),
                "used_memory_bytes": info_mem.get("used_memory", 0),
                "maxmemory_bytes": info_mem.get("maxmemory", 0),
            },
            "cache": {
                "hits": hits,
                "misses": misses,
                "hit_rate_percent": hit_rate,
                "evicted_keys": info_stats.get("evicted_keys", 0),
            },
        }
    except Exception as err:
        return {
            "status": "disconnected",
            "enabled": True,
            "error": str(err),
        }


def check_celery() -> Dict[str, Any]:
    """Check Celery worker availability, queue backlog, and task failure statistics."""
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

    # 2. Query document failure statistics from database
    failed_docs_count = 0
    processing_docs_count = 0
    try:
        from app.core.database import documents_collection
        failed_docs_count = documents_collection.count_documents({"status": "FAILED"})
        processing_docs_count = documents_collection.count_documents({"status": "PROCESSING"})
    except Exception:
        pass

    # 3. Inspect active Celery workers
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
                "failed_documents_count": failed_docs_count,
                "processing_documents_count": processing_docs_count,
            }
        else:
            return {
                "status": "no_workers_active",
                "worker_count": 0,
                "active_workers": [],
                "task_queue_backlog": backlog_count,
                "failed_documents_count": failed_docs_count,
                "processing_documents_count": processing_docs_count,
                "note": "Celery broker reachable but no worker processes currently attached",
            }
    except Exception as err:
        return {
            "status": "unavailable",
            "worker_count": 0,
            "active_workers": [],
            "task_queue_backlog": backlog_count,
            "failed_documents_count": failed_docs_count,
            "processing_documents_count": processing_docs_count,
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
    LLM outages are considered 'degraded' signals and DO NOT fail readiness
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
        from google import genai
        client_genai = genai.Client(api_key=settings.gemini_api_key)
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


def check_disk_and_storage() -> Dict[str, Any]:
    """Inspect server disk capacity and uploaded documents storage footprint."""
    upload_path = Path(settings.upload_dir)
    target_disk = upload_path if upload_path.exists() else Path(".")

    # 1. Host / Container Disk Usage
    try:
        usage = shutil.disk_usage(str(target_disk))
        disk_total_gb = round(usage.total / (1024 ** 3), 2)
        disk_used_gb = round(usage.used / (1024 ** 3), 2)
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_percent = round((usage.used / usage.total) * 100, 2) if usage.total > 0 else 0.0
    except Exception:
        disk_total_gb = disk_used_gb = disk_free_gb = disk_percent = 0.0

    # 2. Upload Storage Folder Footprint
    file_count = 0
    total_bytes = 0
    if upload_path.exists():
        try:
            for root, _, files in os.walk(upload_path):
                for f in files:
                    file_count += 1
                    try:
                        total_bytes += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except Exception:
            pass

    upload_storage_mb = round(total_bytes / (1024 * 1024), 2)

    return {
        "status": "healthy" if disk_percent < 90.0 else "critical" if disk_percent >= 95.0 else "warning",
        "disk": {
            "total_gb": disk_total_gb,
            "used_gb": disk_used_gb,
            "free_gb": disk_free_gb,
            "percent_used": disk_percent,
        },
        "uploads": {
            "directory": settings.upload_dir,
            "file_count": file_count,
            "storage_mb": upload_storage_mb,
            "max_file_size_mb": settings.max_file_size_mb,
            "max_user_storage_mb": settings.max_user_storage_mb,
        },
    }


def evaluate_system_alerts(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates operational metrics against predefined alerting thresholds.
    Ensures zero sensitive data leakage (only components, codes, and actions).
    """
    alerts = []

    # 1. MongoDB Alert
    if report.get("mongodb", {}).get("status") != "connected":
        alerts.append({
            "severity": "CRITICAL",
            "component": "mongodb",
            "code": "DB_DISCONNECTED",
            "message": "MongoDB is unreachable or refusing connections.",
            "action": "Inspect MongoDB container logs and verify connectivity on port 27017.",
        })

    # 2. Disk Space Alert
    disk_percent = report.get("storage", {}).get("disk", {}).get("percent_used", 0.0)
    if disk_percent >= 90.0:
        alerts.append({
            "severity": "CRITICAL" if disk_percent >= 95.0 else "WARNING",
            "component": "disk",
            "code": "DISK_SPACE_LOW",
            "message": f"Server disk usage is at {disk_percent}%.",
            "action": "Clean up unused containers, rotate logs, or expand host volume capacity.",
        })

    # 3. Celery Backlog Alert
    backlog = report.get("celery", {}).get("task_queue_backlog", 0)
    if backlog >= 50:
        alerts.append({
            "severity": "WARNING",
            "component": "celery",
            "code": "HIGH_QUEUE_BACKLOG",
            "message": f"Celery task backlog exceeds threshold ({backlog} tasks queued).",
            "action": "Scale worker concurrency or check for stalled worker instances.",
        })

    # 4. API Error Rate Alert
    api_5xx = report.get("api_telemetry", {}).get("error_rate_5xx_percent", 0.0)
    if api_5xx >= 5.0:
        alerts.append({
            "severity": "WARNING",
            "component": "api",
            "code": "HIGH_5XX_ERROR_RATE",
            "message": f"Server 5xx error rate is elevated ({api_5xx}%).",
            "action": "Inspect backend container logs for unhandled route exceptions.",
        })

    # 5. Redis Memory Alert
    redis_data = report.get("redis", {})
    if redis_data.get("status") == "connected":
        used = redis_data.get("memory", {}).get("used_memory_bytes", 0)
        maxm = redis_data.get("memory", {}).get("maxmemory_bytes", 0)
        if maxm > 0 and (used / maxm) >= 0.90:
            alerts.append({
                "severity": "WARNING",
                "component": "redis",
                "code": "REDIS_MEMORY_PRESSURE",
                "message": "Redis memory utilization exceeds 90% of maxmemory limit.",
                "action": "Verify eviction policy is volatile-lru and adjust cache TTL if needed.",
            })

    # 6. LLM Degraded Alert
    if report.get("llm", {}).get("status") == "degraded":
        alerts.append({
            "severity": "WARNING",
            "component": "llm",
            "code": "LLM_PROVIDER_DEGRADED",
            "message": "Google Gemini upstream API returned error or high latency.",
            "action": "Verify Gemini API quota, network egress, and model status.",
        })

    return alerts


def get_readiness_status() -> Tuple[int, Dict[str, Any]]:
    """
    Kubernetes / Load Balancer Readiness Probe.
    Fails (HTTP 503) only if core persistent data layer (MongoDB) is unavailable.
    """
    mongo_status = check_mongodb()
    redis_status = check_redis()
    faiss_status = check_faiss()
    celery_status = check_celery()
    llm_status = check_llm_provider()

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
    Aggregates process metrics, storage, caching, async workers, LLM signals, telemetry, and alerts.
    """
    liveness = get_liveness_status()
    mongo_status = check_mongodb()
    redis_status = check_redis()
    faiss_status = check_faiss()
    celery_status = check_celery()
    llm_status = check_llm_provider()
    storage_status = check_disk_and_storage()
    api_telemetry = telemetry_collector.get_metrics()

    # Determine overall status
    is_core_down = mongo_status.get("status") != "connected"
    is_degraded = (
        redis_status.get("status") == "disconnected"
        or celery_status.get("status") in ("unavailable", "no_workers_active")
        or llm_status.get("status") == "degraded"
        or storage_status.get("status") in ("warning", "critical")
    )

    if is_core_down:
        overall_status = "unhealthy"
        status_code = 503
    elif is_degraded:
        overall_status = "healthy"
        status_code = 200
    else:
        overall_status = "healthy"
        status_code = 200

    report = {
        "status": overall_status,
        "operational_state": "degraded" if is_degraded else "optimal",
        "process": liveness,
        "api_telemetry": api_telemetry,
        "mongodb": mongo_status,
        "redis": redis_status,
        "celery": celery_status,
        "faiss": faiss_status,
        "llm": llm_status,
        "storage": storage_status,
    }

    report["alerts"] = evaluate_system_alerts(report)
    return status_code, report
