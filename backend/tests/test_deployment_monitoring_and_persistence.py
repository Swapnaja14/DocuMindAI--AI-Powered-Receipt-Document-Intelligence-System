import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.telemetry import TelemetryCollector, telemetry_collector
from app.services import health_service


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Step 15.6 Deployment Monitoring & Telemetry Tests
# ============================================================================

def test_telemetry_collector_accuracy():
    """Verify in-memory telemetry tracks requests, status codes, and latency percentiles."""
    collector = TelemetryCollector(max_samples=100)

    # Record 10 successful requests (latencies: 10, 20, ..., 100 ms)
    for i in range(1, 11):
        collector.record_request(status_code=200, latency_ms=i * 10.0)

    # Record 2 client errors (400, 404)
    collector.record_request(status_code=400, latency_ms=15.0)
    collector.record_request(status_code=404, latency_ms=25.0)

    # Record 1 server error (500)
    collector.record_request(status_code=500, latency_ms=120.0)

    metrics = collector.get_metrics()

    assert metrics["total_requests"] == 13
    assert metrics["status_counts"]["2xx"] == 10
    assert metrics["status_counts"]["4xx"] == 2
    assert metrics["status_counts"]["5xx"] == 1

    # 1 out of 13 = 7.69% 5xx error rate
    assert metrics["error_rate_5xx_percent"] == 7.69
    # 2 out of 13 = 15.38% 4xx error rate
    assert metrics["client_error_rate_4xx_percent"] == 15.38

    # Latencies
    assert metrics["latency_ms"]["avg"] > 0
    assert metrics["latency_ms"]["p50"] > 0
    assert metrics["latency_ms"]["p95"] >= metrics["latency_ms"]["p50"]


def test_health_alerts_endpoint_clean_state(client):
    """Verify /health/alerts returns 'ok' with 0 active alerts when systems are healthy."""
    with patch("app.services.health_service.check_mongodb") as mock_mongo, \
         patch("app.services.health_service.check_redis") as mock_redis, \
         patch("app.services.health_service.check_celery") as mock_celery, \
         patch("app.services.health_service.check_llm_provider") as mock_llm, \
         patch("app.services.health_service.check_disk_and_storage") as mock_disk:

        mock_mongo.return_value = {"status": "connected", "database": "documind", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "connected", "enabled": True, "memory": {"used_memory_bytes": 100, "maxmemory_bytes": 1000}}
        mock_celery.return_value = {"status": "connected", "worker_count": 2, "task_queue_backlog": 0}
        mock_llm.return_value = {"status": "operational"}
        mock_disk.return_value = {"status": "healthy", "disk": {"percent_used": 45.0}}

        response = client.get("/health/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["active_alert_count"] == 0
        assert data["alerts"] == []


def test_health_alerts_endpoint_triggered_state(client):
    """Verify /health/alerts detects and returns CRITICAL and WARNING alert conditions."""
    with patch("app.services.health_service.check_mongodb") as mock_mongo, \
         patch("app.services.health_service.check_redis") as mock_redis, \
         patch("app.services.health_service.check_celery") as mock_celery, \
         patch("app.services.health_service.check_llm_provider") as mock_llm, \
         patch("app.services.health_service.check_disk_and_storage") as mock_disk, \
         patch("app.core.telemetry.telemetry_collector.get_metrics") as mock_telemetry:

        mock_mongo.return_value = {"status": "disconnected", "error": "Connection lost"}
        mock_redis.return_value = {"status": "connected", "enabled": True, "memory": {"used_memory_bytes": 950, "maxmemory_bytes": 1000}}
        mock_celery.return_value = {"status": "connected", "worker_count": 1, "task_queue_backlog": 75}
        mock_llm.return_value = {"status": "degraded"}
        mock_disk.return_value = {"status": "warning", "disk": {"percent_used": 92.5}}
        mock_telemetry.return_value = {"error_rate_5xx_percent": 8.5}

        response = client.get("/health/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alerting"
        assert data["active_alert_count"] >= 3

        codes = [a["code"] for a in data["alerts"]]
        assert "DB_DISCONNECTED" in codes
        assert "DISK_SPACE_LOW" in codes
        assert "HIGH_QUEUE_BACKLOG" in codes
        assert "HIGH_5XX_ERROR_RATE" in codes
        assert "REDIS_MEMORY_PRESSURE" in codes
        assert "LLM_PROVIDER_DEGRADED" in codes


def test_health_metrics_endpoint_structure(client):
    """Verify /health/metrics exposes fine-grained telemetry for Prometheus/Datadog scraping."""
    response = client.get("/health/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "api_telemetry" in data
    assert "total_requests" in data["api_telemetry"]
    assert "latency_ms" in data["api_telemetry"]
    assert "mongodb" in data
    assert "redis" in data
    assert "celery" in data
    assert "storage" in data
    assert "faiss" in data


def test_no_sensitive_document_data_in_monitoring(client):
    """
    Step 15.6 Critical Requirement:
    Avoid collecting unnecessary sensitive document data in monitoring systems.
    Telemetry must expose ONLY operational signals, zero invoice/receipt payloads.
    """
    response = client.get("/health")
    assert response.status_code == 200
    content_str = response.text.lower()

    # Verify no sensitive keywords or leakages occur
    prohibited_keywords = [
        "password",
        "secret",
        "api_key",
        "ssn",
        "credit_card",
        "invoice_text",
        "raw_text",
        "extracted_data",
        "bearer ",
    ]
    for keyword in prohibited_keywords:
        assert keyword not in content_str, f"Found sensitive keyword '{keyword}' in health report!"


# ============================================================================
# Step 15.5 Persistence & Volume Validation Tests
# ============================================================================

def test_storage_and_disk_monitoring():
    """Verify check_disk_and_storage returns structured disk and upload directory statistics."""
    storage_info = health_service.check_disk_and_storage()
    assert "status" in storage_info
    assert "disk" in storage_info
    assert "total_gb" in storage_info["disk"]
    assert "percent_used" in storage_info["disk"]
    assert "uploads" in storage_info
    assert "directory" in storage_info["uploads"]
    assert "file_count" in storage_info["uploads"]
    assert "storage_mb" in storage_info["uploads"]
