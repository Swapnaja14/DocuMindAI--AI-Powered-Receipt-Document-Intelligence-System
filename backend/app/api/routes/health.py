from fastapi import APIRouter, Response
from app.services.health_service import (
    get_liveness_status,
    get_readiness_status,
    get_full_health_report,
)
from app.core.telemetry import telemetry_collector

router = APIRouter(tags=["Health & Monitoring"])


@router.get("/health/live", summary="Liveness Probe")
def liveness_check():
    """
    Process liveness check for Kubernetes/Docker.
    Returns 200 as long as the process is alive and event loop is responsive.
    """
    return get_liveness_status()


@router.get("/health/ready", summary="Readiness Probe")
def readiness_check(response: Response):
    """
    Readiness probe for Kubernetes/Load Balancer.
    Establishes if the application is ready to accept user requests.
    Returns 200 when ready, 503 when core datastore is unreachable.
    Temporary third-party LLM outages do not fail readiness.
    """
    status_code, payload = get_readiness_status()
    response.status_code = status_code
    return payload


@router.get("/health", summary="Operational Health Diagnostics")
def full_health_check(response: Response):
    """
    Comprehensive operational health status endpoint.
    Aggregates MongoDB, Redis, FAISS vector store, Celery workers, backlog, storage, telemetry, and alerts.
    """
    status_code, payload = get_full_health_report()
    response.status_code = status_code
    return payload


@router.get("/health/alerts", summary="Active System Alerts")
def alerts_check():
    """
    Proactive operational alert status endpoint.
    Evaluates system metrics against alert thresholds and returns active action items.
    """
    _, report = get_full_health_report()
    alerts = report.get("alerts", [])
    return {
        "status": "alerting" if any(a.get("severity") == "CRITICAL" for a in alerts) else "warning" if alerts else "ok",
        "active_alert_count": len(alerts),
        "alerts": alerts,
    }


@router.get("/health/metrics", summary="Deployment & Request Telemetry Metrics")
def metrics_check():
    """
    Fine-grained deployment metrics for monitoring collectors (Prometheus, Datadog).
    Exposes request throughput, latency percentiles, error rates, and resource utilization.
    """
    _, report = get_full_health_report()
    return {
        "api_telemetry": report.get("api_telemetry", {}),
        "mongodb": report.get("mongodb", {}),
        "redis": report.get("redis", {}),
        "celery": report.get("celery", {}),
        "storage": report.get("storage", {}),
        "faiss": report.get("faiss", {}),
    }
