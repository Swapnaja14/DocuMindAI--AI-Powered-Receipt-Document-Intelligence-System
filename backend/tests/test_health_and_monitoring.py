import pytest
import warnings
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, settings
from app.services import health_service


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Step 13.5: Environment & Secrets Configuration Tests
# ============================================================================

def test_settings_production_debug_mode_enforcement():
    """Verify debug mode is forced to False when environment is production."""
    prod_settings = Settings(
        environment="production",
        debug=True,  # Attempt to enable debug in production
        jwt_secret_key="a_very_strong_random_secret_key_for_testing_12345678",
    )
    assert prod_settings.is_production is True
    assert prod_settings.debug is False  # Forced off


def test_settings_production_default_secret_warning():
    """Verify warning is emitted if production environment uses default JWT secret."""
    with pytest.warns(UserWarning, match="SECURITY WARNING: Production environment detected"):
        Settings(
            environment="production",
            debug=False,
            jwt_secret_key="default_secret_key_change_in_production",
        )


def test_cors_configuration(client):
    """Verify CORS headers reflect configured allowed origins."""
    # Test allowed origin
    response = client.get(
        "/health/live",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"

    # Test another origin not in allowed list
    response_unauth = client.get(
        "/health/live",
        headers={"Origin": "http://malicious-site.example.com"},
    )
    assert response_unauth.status_code == 200
    # Disallowed origin should not have access-control-allow-origin matching malicious site
    assert response_unauth.headers.get("access-control-allow-origin") != "http://malicious-site.example.com"


# ============================================================================
# Step 13.6: Health Checks & Operational Monitoring Tests
# ============================================================================

def test_liveness_check_always_returns_alive(client):
    """
    Step 13.6: Liveness probe must verify process is alive.
    Must never check external dependencies or fail on downstream outages.
    """
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert "pid" in data
    assert "environment" in data


def test_readiness_check_when_database_is_connected(client):
    """Readiness probe returns 200 when MongoDB is reachable."""
    with patch("app.services.health_service.check_mongodb") as mock_mongo:
        mock_mongo.return_value = {"status": "connected", "database": "documind", "latency_ms": 1.2}
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["mongodb"]["status"] == "connected"
        assert "redis" in data
        assert "celery" in data
        assert "llm" in data


def test_readiness_check_fails_when_mongodb_is_disconnected(client):
    """Readiness probe returns 503 when core database (MongoDB) is down."""
    with patch("app.services.health_service.check_mongodb") as mock_mongo:
        mock_mongo.return_value = {"status": "disconnected", "error": "Connection refused"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unready"
        assert data["mongodb"]["status"] == "disconnected"


def test_readiness_check_does_not_fail_on_llm_outage(client):
    """
    Step 13.6 CRITICAL: Avoid making temporary third-party LLM outages
    cause unnecessary application restarts or readiness probe failures.
    """
    with patch("app.services.health_service.check_mongodb") as mock_mongo, \
         patch("app.services.health_service.check_llm_provider") as mock_llm:
        mock_mongo.return_value = {"status": "connected", "database": "documind", "latency_ms": 1.5}
        mock_llm.return_value = {
            "provider": "google-gemini",
            "model": "gemini-3.5-flash-lite",
            "configured": True,
            "status": "degraded",
            "error": "503 Service Unavailable: High load on Google Gemini upstream",
        }

        response = client.get("/health/ready")
        # App readiness must remain 200 OK despite LLM provider outage
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["llm"]["status"] == "degraded"


def test_comprehensive_operational_health_report(client):
    """
    Test full /health endpoint with signals for process, MongoDB, Redis,
    Celery worker availability, task queue backlog, and LLM provider.
    """
    with patch("app.services.health_service.check_mongodb") as mock_mongo, \
         patch("app.services.health_service.check_redis") as mock_redis, \
         patch("app.services.health_service.check_celery") as mock_celery, \
         patch("app.services.health_service.check_llm_provider") as mock_llm:

        mock_mongo.return_value = {"status": "connected", "database": "documind", "latency_ms": 2.1}
        mock_redis.return_value = {"status": "connected", "enabled": True, "latency_ms": 0.8}
        mock_celery.return_value = {
            "status": "connected",
            "worker_count": 2,
            "active_workers": ["celery@worker1", "celery@worker2"],
            "task_queue_backlog": 0,
        }
        mock_llm.return_value = {
            "provider": "google-gemini",
            "model": "gemini-3.5-flash-lite",
            "configured": True,
            "status": "operational",
            "latency_ms": 45.0,
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["operational_state"] == "optimal"
        assert "process" in data
        assert data["process"]["status"] == "alive"
        assert data["mongodb"]["status"] == "connected"
        assert data["redis"]["status"] == "connected"
        assert data["celery"]["worker_count"] == 2
        assert data["celery"]["task_queue_backlog"] == 0
        assert data["llm"]["status"] == "operational"
        assert "faiss" in data


def test_celery_task_backlog_reporting():
    """Verify Celery task queue backlog is correctly reported from broker."""
    with patch("redis.from_url") as mock_redis_from_url, \
         patch("app.celery_app.celery_app.control.inspect") as mock_inspect:

        mock_r = MagicMock()
        mock_r.llen.return_value = 5  # 5 tasks queued in Celery backlog
        mock_redis_from_url.return_value = mock_r

        mock_inspector = MagicMock()
        mock_inspector.ping.return_value = {"celery@node1": {"ok": "pong"}}
        mock_inspect.return_value = mock_inspector

        celery_status = health_service.check_celery()
        assert celery_status["status"] == "connected"
        assert celery_status["worker_count"] == 1
        assert celery_status["task_queue_backlog"] == 5
