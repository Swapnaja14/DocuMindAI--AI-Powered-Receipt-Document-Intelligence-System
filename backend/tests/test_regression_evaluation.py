import asyncio
import os
import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluation.dataset import load_dev_benchmark, load_holdout_benchmark, get_all_evaluation_documents
from evaluation.evaluate_rag import RAGEvaluator


@pytest.fixture(scope="module")
def evaluator(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("regression_eval")
    ev = RAGEvaluator(temp_dir=temp_dir)
    ev.seed_corpus()
    return ev


@pytest.fixture(scope="module")
def dev_benchmark():
    return load_dev_benchmark()


@pytest.fixture(scope="module")
def holdout_benchmark():
    return load_holdout_benchmark()


def test_extraction_accuracy_and_arithmetic_consistency(evaluator):
    """
    Step 12.7: Evaluate field-level extraction accuracy and arithmetic validation.
    """
    res = evaluator.evaluate_extraction_accuracy()
    acc = res["field_accuracy"]

    assert res["total_documents"] == 8
    assert acc["vendor_accuracy"] == 1.0
    assert acc["date_accuracy"] == 1.0
    assert acc["total_numeric_accuracy"] == 1.0
    assert acc["currency_accuracy"] == 1.0
    assert acc["invoice_number_accuracy"] == 1.0
    assert acc["arithmetic_consistency_rate"] == 1.0
    assert acc["overall_perfect_rate"] == 1.0
    assert len(res["validation_errors"]) == 0


@pytest.mark.asyncio
async def test_retrieval_metrics_meet_minimum_targets(evaluator, dev_benchmark):
    """
    Step 12.7: Evaluate Dev retrieval Recall@5, Precision@5, and MRR.
    """
    k5_res = await evaluator.evaluate_retrieval(dev_benchmark, top_k=5)

    assert k5_res["total_questions"] == 32
    # Targets: Recall@5 >= 85%, Precision@5 >= 25%, MRR >= 0.70
    assert k5_res["mean_recall_at_k"] >= 0.85
    assert k5_res["mean_precision_at_k"] >= 0.25
    assert k5_res["mean_mrr"] >= 0.70

    # Expanded k=8 evaluation
    k8_res = await evaluator.evaluate_retrieval(dev_benchmark, top_k=8)
    assert k8_res["mean_recall_at_k"] >= k5_res["mean_recall_at_k"]


@pytest.mark.asyncio
async def test_holdout_retrieval_and_generalization(evaluator, holdout_benchmark):
    """
    Step 12.7: Evaluate generalization on unseen holdout benchmark.
    """
    holdout_res = await evaluator.evaluate_retrieval(holdout_benchmark, top_k=5)

    assert holdout_res["total_questions"] == 16
    assert holdout_res["mean_recall_at_k"] >= 0.90
    assert holdout_res["mean_mrr"] >= 0.75


@pytest.mark.asyncio
async def test_citation_grounding_and_tenant_isolation(evaluator, holdout_benchmark):
    """
    Step 12.7: Verify 100% tenant ownership, citation alignment, and numeric fidelity.
    """
    grounding_res = await evaluator.evaluate_answers_and_grounding(holdout_benchmark)
    rates = grounding_res["accuracy_rates"]

    assert rates["ownership_accuracy"] == 1.0
    assert rates["citation_grounding_accuracy"] == 1.0
    assert rates["numeric_date_fidelity"] == 1.0
    assert rates["abstention_accuracy"] == 1.0
    assert len(grounding_res["issues"]) == 0


@pytest.mark.asyncio
async def test_latency_and_token_estimation_recorded(evaluator, dev_benchmark):
    """
    Step 12.7: Ensure retrieval latency and token usage are profiled.
    """
    res = await evaluator.evaluate_retrieval(dev_benchmark, top_k=5)
    lat = res["latency"]
    tok = res["token_estimation"]

    assert "mean_ms" in lat and 0 < lat["mean_ms"] < 1000.0  # Measured retrieval latency on CPU
    assert "p50_ms" in lat
    assert "p95_ms" in lat
    assert tok["estimated_query_tokens"] > 0
    assert tok["avg_context_tokens_per_query"] > 0
