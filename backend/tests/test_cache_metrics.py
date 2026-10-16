import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.users import get_current_user
from app.main import app
from app.services.cache_metrics import cache_metrics
from app.services.cache_service import invalidate_user_cache_sync

# Prevent MongoDB connection timeout during test lifespan startup
patch("app.main.create_indexes", lambda: None).start()


def get_mock_user():
    return {
        "_id": ObjectId("65c000000000000000000099"),
        "id": "65c000000000000000000099",
        "email": "metrics_user@example.com",
        "role": "user",
    }


def test_metrics_recording_and_hit_ratio():
    cache_metrics.reset()

    # Record 3 hits with latencies
    cache_metrics.record_hit(12.5)
    cache_metrics.record_hit(15.0)
    cache_metrics.record_hit(10.0)

    # Record 1 miss with latency
    cache_metrics.record_miss(250.0)

    summary = cache_metrics.get_summary()
    assert summary["hits"] == 3
    assert summary["misses"] == 1
    # Hit Ratio = 3 / (3 + 1) * 100 = 75.0%
    assert summary["hit_ratio_percent"] == 75.0
    assert summary["avg_hit_latency_ms"] == 12.5
    assert summary["avg_miss_latency_ms"] == 250.0


def test_errors_separated_from_misses():
    cache_metrics.reset()

    # 1 hit, 1 miss
    cache_metrics.record_hit(5.0)
    cache_metrics.record_miss(100.0)

    # Record read and write errors
    cache_metrics.record_read_error(ConnectionError("Redis down"))
    cache_metrics.record_write_error(TimeoutError("Redis timeout"))

    summary = cache_metrics.get_summary()
    assert summary["hits"] == 1
    assert summary["misses"] == 1
    assert summary["read_errors"] == 1
    assert summary["write_errors"] == 1

    # Errors must NOT count as ordinary misses: hit ratio remains 50.0%
    assert summary["hit_ratio_percent"] == 50.0


def test_invalidations_and_invalid_entries_and_report_format():
    cache_metrics.reset()

    cache_metrics.record_hit(8.0)
    cache_metrics.record_miss(150.0)
    cache_metrics.record_invalidation(3)
    cache_metrics.record_invalid_entry()

    report = cache_metrics.format_report()
    assert "RAG cache metrics" in report
    assert "Cache hits:          1" in report
    assert "Cache misses:        1" in report
    assert "Cache read errors:   0" in report
    assert "Cache write errors:  0" in report
    assert "Invalidations:       3" in report
    assert "Invalid entries:     1" in report
    assert "Hit ratio:           50.0%" in report


def test_rag_endpoint_observability_integration():
    cache_metrics.reset()
    user = get_mock_user()
    user_id = str(user["_id"])
    invalidate_user_cache_sync(user_id)

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_metric_1",
                "document_id": "doc_metric_1",
                "filename": "server_bill.pdf",
                "page": 1,
                "text": "Server cost: $120",
                "score": 0.95,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "Server cost was $120.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    payload = {"question": "How much was the server cost?"}

    # 1. First request -> Cache Miss
    resp1 = client.post("/api/v1/rag/ask", json=payload)
    assert resp1.status_code == 200
    assert cache_metrics.misses >= 1
    assert len(cache_metrics.miss_latencies_ms) >= 1

    # 2. Second request -> Cache Hit
    resp2 = client.post("/api/v1/rag/ask", json=payload)
    assert resp2.status_code == 200
    assert cache_metrics.hits >= 1
    assert len(cache_metrics.hit_latencies_ms) >= 1

    # 3. Check /api/v1/rag/cache/metrics endpoint
    metrics_resp = client.get("/api/v1/rag/cache/metrics")
    assert metrics_resp.status_code == 200
    data = metrics_resp.json()
    assert "summary" in data
    assert "report" in data
    assert data["summary"]["hits"] >= 1
    assert data["summary"]["misses"] >= 1
    assert "RAG cache metrics" in data["report"]
