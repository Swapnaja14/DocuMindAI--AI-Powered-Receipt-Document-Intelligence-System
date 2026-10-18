import pytest
from evaluation import (
    EVALUATION_DOCUMENTS,
    EvaluationCategory,
    load_dev_benchmark,
    load_holdout_benchmark,
)


def test_evaluation_documents_integrity():
    """Verify document corpus completeness and required fields."""
    assert len(EVALUATION_DOCUMENTS) == 8
    doc_ids = set()

    for doc in EVALUATION_DOCUMENTS:
        assert doc["document_id"]
        assert doc["document_id"] not in doc_ids
        doc_ids.add(doc["document_id"])

        assert doc["vendor"]
        assert doc["date"]
        assert doc["currency"] in {"USD", "INR", "EUR"}
        assert isinstance(doc["total"], (int, float))
        assert doc["total"] > 0
        assert len(doc["raw_text"]) > 50


def test_dev_benchmark_validation_and_categories():
    """Verify dev benchmark has 32 items covering all 8 categories."""
    benchmark = load_dev_benchmark()
    assert benchmark.name == "dev_benchmark"
    assert len(benchmark.items) == 32

    category_counts = {}
    for item in benchmark.items:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
        assert item.question.strip()
        assert item.expected_answer.strip()
        assert item.evaluation_criteria.strip()

        # Check supporting doc IDs exist
        for doc_id in item.supporting_document_ids:
            assert any(d["document_id"] == doc_id for d in EVALUATION_DOCUMENTS)

        # Check missing information category specifies abstention
        if item.category == EvaluationCategory.MISSING_INFORMATION:
            assert item.should_abstain is True

    # All 8 categories must be present with exactly 4 questions each
    assert len(category_counts) == 8
    for cat in EvaluationCategory:
        assert category_counts[cat] == 4


def test_holdout_benchmark_validation_and_categories():
    """Verify holdout benchmark has 16 items covering all 8 categories."""
    benchmark = load_holdout_benchmark()
    assert benchmark.name == "holdout_benchmark"
    assert len(benchmark.items) == 16

    category_counts = {}
    for item in benchmark.items:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
        assert item.question.strip()
        assert item.expected_answer.strip()
        assert item.evaluation_criteria.strip()

        for doc_id in item.supporting_document_ids:
            assert any(d["document_id"] == doc_id for d in EVALUATION_DOCUMENTS)

        if item.category == EvaluationCategory.MISSING_INFORMATION:
            assert item.should_abstain is True

    assert len(category_counts) == 8
    for cat in EvaluationCategory:
        assert category_counts[cat] == 2


def test_no_leakage_between_dev_and_holdout():
    """Ensure holdout set questions and IDs are strictly disjoint from dev set."""
    dev = load_dev_benchmark()
    holdout = load_holdout_benchmark()

    dev_ids = {item.id for item in dev.items}
    holdout_ids = {item.id for item in holdout.items}
    assert len(dev_ids.intersection(holdout_ids)) == 0

    dev_questions = {item.question.strip().lower() for item in dev.items}
    holdout_questions = {item.question.strip().lower() for item in holdout.items}
    assert len(dev_questions.intersection(holdout_questions)) == 0

    total_questions = len(dev.items) + len(holdout.items)
    assert total_questions == 48
    assert 30 <= total_questions <= 50
