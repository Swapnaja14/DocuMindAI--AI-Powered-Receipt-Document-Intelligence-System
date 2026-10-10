from app.schemas.rag import RAGAskResponse
from app.services.rag_citations import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    build_rag_response,
    is_insufficient_evidence_response,
    resolve_grounded_answer,
    validate_citations,
)


SAMPLE_SOURCES = [
    {
        "source_id": "S1",
        "document_id": "doc_101",
        "filename": "apple_laptop.pdf",
        "page": 1,
        "chunk_id": "c_1",
        "snippet": "MacBook Pro total: ₹1,99,000",
    },
    {
        "source_id": "S2",
        "document_id": "doc_102",
        "filename": "dell_laptop.pdf",
        "page": 2,
        "chunk_id": "c_2",
        "snippet": "Dell XPS total: ₹1,45,000",
    },
]


def test_validate_citations_valid_and_order():
    citations = ["S2", "S1"]
    validated = validate_citations(citations, SAMPLE_SOURCES)

    assert len(validated) == 2
    assert validated[0]["source_id"] == "S2"
    assert validated[1]["source_id"] == "S1"


def test_validate_citations_filters_invalid_and_duplicates():
    citations = ["S1", "S99", "S1", "UNKNOWN", "[S2]"]
    validated = validate_citations(citations, SAMPLE_SOURCES)

    assert len(validated) == 2
    assert validated[0]["source_id"] == "S1"
    assert validated[1]["source_id"] == "S2"


def test_validate_citations_empty():
    assert validate_citations([], SAMPLE_SOURCES) == []
    assert validate_citations(["S1"], []) == []


def test_is_insufficient_evidence_response():
    assert is_insufficient_evidence_response("The information is unavailable in the retrieved documents.") is True
    assert is_insufficient_evidence_response("No receipts found for coffee purchases.") is True
    assert is_insufficient_evidence_response("Could not find any laptop purchases.") is True
    assert is_insufficient_evidence_response("The highest total was ₹1,99,000.") is False


def test_resolve_grounded_answer_with_valid_citations():
    answer = "The highest purchase was MacBook Pro at ₹1,99,000."
    model_citations = ["S1"]

    final_answer, valid_sources = resolve_grounded_answer(
        answer=answer,
        model_citations=model_citations,
        sources=SAMPLE_SOURCES,
    )

    assert final_answer == answer
    assert len(valid_sources) == 1
    assert valid_sources[0]["source_id"] == "S1"


def test_resolve_grounded_answer_rejects_hallucinated_citations():
    # Model claims a fact but cites non-existent sources
    answer = "The highest purchase was Lenovo ThinkPad at ₹2,50,000."
    model_citations = ["S99", "FAKE_DOC"]

    final_answer, valid_sources = resolve_grounded_answer(
        answer=answer,
        model_citations=model_citations,
        sources=SAMPLE_SOURCES,
    )

    # Must be replaced with insufficient evidence message
    assert final_answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert valid_sources == []


def test_resolve_grounded_answer_rejects_missing_citations_for_substantive_claim():
    # Model claims a fact without citing any sources
    answer = "The highest purchase was MacBook Pro at ₹1,99,000."
    model_citations = []

    final_answer, valid_sources = resolve_grounded_answer(
        answer=answer,
        model_citations=model_citations,
        sources=SAMPLE_SOURCES,
    )

    # Must be rejected because substantive answer cites no sources
    assert final_answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert valid_sources == []


def test_resolve_grounded_answer_preserves_legitimate_missing_evidence_response():
    # Model explicitly states evidence is unavailable and cites []
    answer = "The requested information is unavailable in the retrieved documents."
    model_citations = []

    final_answer, valid_sources = resolve_grounded_answer(
        answer=answer,
        model_citations=model_citations,
        sources=SAMPLE_SOURCES,
    )

    assert final_answer == answer
    assert valid_sources == []


def test_build_rag_response():
    answer = "MacBook Pro total was ₹1,99,000."
    model_citations = ["S1"]

    response = build_rag_response(
        answer=answer,
        model_citations=model_citations,
        sources=SAMPLE_SOURCES,
        top_k=5,
    )

    assert isinstance(response, RAGAskResponse)
    assert response.answer == answer
    assert len(response.sources) == 1
    assert response.sources[0].document_id == "doc_101"
    assert response.sources[0].filename == "apple_laptop.pdf"
    assert response.retrieval.top_k == 5
    assert response.retrieval.sources_used == 1
