import pytest
from pydantic import ValidationError

from app.schemas.rag import (
    RAGAskRequest,
    RAGAskResponse,
    RAGSource,
    RetrievalMetadata,
)


def test_rag_ask_request_valid():
    req = RAGAskRequest(
        question="Which receipt had the highest total among my laptop purchases?",
        top_k=5,
    )
    assert req.question == "Which receipt had the highest total among my laptop purchases?"
    assert req.top_k == 5


def test_rag_ask_request_defaults():
    req = RAGAskRequest(question="Where was my last coffee purchased?")
    assert req.top_k == 5


def test_rag_ask_request_validation_errors():
    # Question too short (< 3 chars)
    with pytest.raises(ValidationError):
        RAGAskRequest(question="hi")

    # top_k too low (< 1)
    with pytest.raises(ValidationError):
        RAGAskRequest(question="Valid question?", top_k=0)

    # top_k too high (> 10)
    with pytest.raises(ValidationError):
        RAGAskRequest(question="Valid question?", top_k=15)


def test_rag_ask_response_structure():
    response = RAGAskResponse(
        answer="The highest laptop purchase was ₹85,000.",
        sources=[
            RAGSource(
                document_id="doc_183",
                filename="laptop_receipt.pdf",
                page=1,
                chunk_id="chunk_abc123",
                snippet="Laptop purchase total: INR 85,000",
            )
        ],
        retrieval=RetrievalMetadata(
            top_k=5,
            sources_used=1,
        ),
    )
    data = response.model_dump()
    assert data["answer"] == "The highest laptop purchase was ₹85,000."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["document_id"] == "doc_183"
    assert data["sources"][0]["page"] == 1
    assert data["retrieval"]["top_k"] == 5
    assert data["retrieval"]["sources_used"] == 1
