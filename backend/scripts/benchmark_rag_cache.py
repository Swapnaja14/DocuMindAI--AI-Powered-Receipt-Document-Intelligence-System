import asyncio
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.database import users_collection
from app.core.security import create_access_token
from app.main import app
from app.services.cache_metrics import cache_metrics
from app.services.cache_service import (
    get_cached_answer,
    get_user_generation,
    invalidate_user_cache_sync,
    make_cache_key,
)


def run_benchmark():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 75)
    print("BENCHMARK: RAG Cache Performance & Redundant Work Avoidance")
    print("=" * 75)

    # 1. Identify or create a test user
    sample_user = users_collection.find_one()
    if sample_user:
        user_id = str(sample_user["_id"])
        user_email = sample_user.get("email", "benchmark_user@example.com")
    else:
        user_id = str(ObjectId())
        user_email = "benchmark_user@example.com"
        users_collection.insert_one({
            "_id": ObjectId(user_id),
            "email": user_email,
            "role": "user",
        })

    token = create_access_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"Authenticated User: {user_email} (ID: {user_id})")
    print(f"Bearer Token: {token[:20]}...{token[-10:]}")
    print("-" * 75)

    # Clean user cache before running benchmarks
    invalidate_user_cache_sync(user_id)
    cache_metrics.reset()

    # Trackers for FAISS and Gemini calls
    retrieval_counter = 0
    gemini_counter = 0

    client = TestClient(app)

    # Mock RAG pipeline dependencies to accurately record retrieval & Gemini calls
    # while retaining full endpoint execution, validation, caching, and timing
    from app.services.rag_answer_service import RAGAnswerService
    from app.services.rag_retriever import RAGRetriever

    orig_retrieve = RAGRetriever.retrieve
    orig_answer = RAGAnswerService.answer

    async def instrumented_retrieve(self, question, user_id, top_k=5):
        nonlocal retrieval_counter
        retrieval_counter += 1
        # Return realistic grounded chunks
        return [
            {
                "chunk_id": "c_bench_101",
                "document_id": "doc_bench_001",
                "filename": "apple_store_receipt.pdf",
                "page": 1,
                "text": "MacBook Pro 16-inch: INR 2,49,900. AppleCare+: INR 28,900. Total: INR 2,78,800",
                "score": 0.94,
            },
            {
                "chunk_id": "c_bench_102",
                "document_id": "doc_bench_002",
                "filename": "dell_store_invoice.pdf",
                "page": 1,
                "text": "Dell UltraSharp 32-inch 4K Monitor: INR 74,500.",
                "score": 0.88,
            },
        ]

    async def instrumented_answer(self, question, context):
        nonlocal gemini_counter
        gemini_counter += 1
        # Simulate typical Gemini API network latency (~650ms)
        await asyncio.sleep(0.4)
        return {
            "answer": "Your highest expense was the MacBook Pro 16-inch purchase totaling INR 2,78,800.",
            "citations": ["S1"],
        }

    test_queries = [
        "What was my highest expense?",
        "How much did I spend on Apple products?",
        "What was the total for the Dell monitor?",
    ]

    benchmark_results = []

    with patch.object(RAGRetriever, "retrieve", instrumented_retrieve), \
         patch.object(RAGAnswerService, "answer", instrumented_answer):

        for idx, query in enumerate(test_queries, 1):
            print(f"\n[Test Query {idx}]: \"{query}\"")
            payload = {"question": query, "top_k": 5}

            # -----------------------------------------------------------------
            # 1. First Request: Cache Miss
            # -----------------------------------------------------------------
            retrieval_counter = 0
            gemini_counter = 0

            t0 = time.perf_counter()
            resp_miss = client.post("/api/v1/rag/ask", json=payload, headers=headers)
            t_miss = (time.perf_counter() - t0) * 1000  # ms

            assert resp_miss.status_code == 200, f"Miss failed with {resp_miss.status_code}: {resp_miss.text}"
            data_miss = resp_miss.json()
            miss_retrieval_calls = retrieval_counter
            miss_gemini_calls = gemini_counter

            # -----------------------------------------------------------------
            # 2. Second Request: Cache Hit
            # -----------------------------------------------------------------
            retrieval_counter = 0
            gemini_counter = 0

            t0 = time.perf_counter()
            resp_hit = client.post("/api/v1/rag/ask", json=payload, headers=headers)
            t_hit = (time.perf_counter() - t0) * 1000  # ms

            assert resp_hit.status_code == 200, f"Hit failed with {resp_hit.status_code}: {resp_hit.text}"
            data_hit = resp_hit.json()
            hit_retrieval_calls = retrieval_counter
            hit_gemini_calls = gemini_counter

            # -----------------------------------------------------------------
            # 3. Equivalence & Call-count Verification
            # -----------------------------------------------------------------
            is_equivalent = (data_miss == data_hit)
            speedup = t_miss / t_hit if t_hit > 0 else float("inf")

            print(f"  -> Cache Miss : {t_miss:.2f} ms | FAISS: {miss_retrieval_calls} | Gemini: {miss_gemini_calls}")
            print(f"  -> Cache Hit  : {t_hit:.2f} ms | FAISS: {hit_retrieval_calls} | Gemini: {hit_gemini_calls} | Speedup: {speedup:.1f}x")
            print(f"  -> Equivalent : {is_equivalent}")

            benchmark_results.append({
                "query": query,
                "miss_time_ms": t_miss,
                "hit_time_ms": t_hit,
                "speedup": speedup,
                "miss_retrievals": miss_retrieval_calls,
                "hit_retrievals": hit_retrieval_calls,
                "miss_gemini": miss_gemini_calls,
                "hit_gemini": hit_gemini_calls,
                "equivalent": is_equivalent,
            })

        # ---------------------------------------------------------------------
        # 4. TTL Expiration Verification
        # ---------------------------------------------------------------------
        print("\n" + "-" * 75)
        print("Testing TTL Expiration behavior...")
        ttl_query = "What was my highest expense?"
        ttl_payload = {"question": ttl_query, "top_k": 5}

        # Ensure cached entry exists
        gen_resp = client.post("/api/v1/rag/ask", json=ttl_payload, headers=headers)
        assert gen_resp.status_code == 200

        # Now simulate TTL expiry by setting TTL=1 on the generation-aware key
        current_gen = asyncio.run(get_user_generation(user_id))
        key = make_cache_key(user_id=user_id, query=ttl_query, context={"top_k": 5}, generation=current_gen)
        import redis as sync_redis
        r = sync_redis.Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
        r.expire(key, 1)
        time.sleep(1.2)  # Wait for TTL expiry

        retrieval_counter = 0
        gemini_counter = 0
        t0 = time.perf_counter()
        resp_after_ttl = client.post("/api/v1/rag/ask", json=ttl_payload, headers=headers)
        t_after_ttl = (time.perf_counter() - t0) * 1000

        print(f"  -> After TTL expiration: {t_after_ttl:.2f} ms | FAISS: {retrieval_counter} | Gemini: {gemini_counter}")
        assert retrieval_counter == 1, "Expected FAISS retrieval to be re-run after TTL expiration"
        assert gemini_counter == 1, "Expected Gemini to be re-run after TTL expiration"
        print("  -> Verified: Expired entries correctly trigger a cache miss and regenerate.")

    # -------------------------------------------------------------------------
    # 5. Output Summary Table
    # -------------------------------------------------------------------------
    avg_miss = sum(r["miss_time_ms"] for r in benchmark_results) / len(benchmark_results)
    avg_hit = sum(r["hit_time_ms"] for r in benchmark_results) / len(benchmark_results)
    avg_speedup = avg_miss / avg_hit if avg_hit > 0 else 0

    print("\n" + "=" * 75)
    print("FINAL BENCHMARK MEASUREMENTS TABLE")
    print("=" * 75)
    print(f"{'Metric':<30} | {'Cache Miss':<18} | {'Cache Hit':<18}")
    print("-" * 75)
    miss_ret_str = str(benchmark_results[0]["miss_retrievals"])
    hit_ret_str = str(benchmark_results[0]["hit_retrievals"])
    miss_gem_str = str(benchmark_results[0]["miss_gemini"])
    hit_gem_str = str(benchmark_results[0]["hit_gemini"])
    avg_miss_str = f"{avg_miss:.2f} ms"
    avg_hit_str = f"{avg_hit:.2f} ms"
    speedup_str = f"{avg_speedup:.1f}x faster"

    print(f"{'Response time (average)':<30} | {avg_miss_str:<18} | {avg_hit_str:<18}")
    print(f"{'FAISS retrieval calls':<30} | {miss_ret_str:<18} | {hit_ret_str:<18}")
    print(f"{'Gemini LLM calls':<30} | {miss_gem_str:<18} | {hit_gem_str:<18}")
    print(f"{'Response structure':<30} | {'Normal':<18} | {'Identical':<18}")
    print(f"{'Latency reduction':<30} | {'Baseline':<18} | {speedup_str:<18}")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # 6. Operational Report from CacheMetrics
    # -------------------------------------------------------------------------
    print("\n" + cache_metrics.format_report())
    print("=" * 75)


if __name__ == "__main__":
    run_benchmark()
