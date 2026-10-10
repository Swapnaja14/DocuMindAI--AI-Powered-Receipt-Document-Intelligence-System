import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.services.rag_answer_service import (
    RAGAnswerService,
    RAG_SYSTEM_PROMPT,
)


def run_async(coro):
    return asyncio.run(coro)


def test_rag_answer_service_valid_response():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value=json.dumps({
                "answer": "The total for your laptop was INR 85,000.",
                "citations": ["S1"],
            })
        )

        service = RAGAnswerService(gemini_client=mock_client)
        result = await service.answer(
            question="What was the total?",
            context="[S1] Laptop purchase total: INR 85,000",
        )

        assert result["answer"] == "The total for your laptop was INR 85,000."
        assert result["citations"] == ["S1"]
        mock_client.generate_text.assert_awaited_once()

    run_async(_run())


def test_rag_answer_service_markdown_fenced_json():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value="""```json
{
  "answer": "The laptop cost ₹85,000.",
  "citations": ["[S1]", "[S2]"]
}
```"""
        )

        service = RAGAnswerService(gemini_client=mock_client)
        result = await service.answer(
            question="How much?",
            context="[S1] ... [S2] ...",
        )

        assert result["answer"] == "The laptop cost ₹85,000."
        # Bracketed IDs should be normalized
        assert result["citations"] == ["S1", "S2"]

    run_async(_run())


def test_rag_answer_service_invalid_json_raises_value_error():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value="Sorry, I cannot answer that."
        )

        service = RAGAnswerService(gemini_client=mock_client)
        with pytest.raises(ValueError, match="Gemini returned an invalid JSON response"):
            await service.answer(
                question="What was the total?",
                context="Some context",
            )

    run_async(_run())


def test_rag_answer_service_missing_answer_raises_value_error():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value=json.dumps({
                "citations": ["S1"]
            })
        )

        service = RAGAnswerService(gemini_client=mock_client)
        with pytest.raises(ValueError, match="Missing answer in Gemini response"):
            await service.answer(
                question="What was the total?",
                context="Some context",
            )

    run_async(_run())


def test_rag_answer_service_invalid_citations_raises_value_error():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value=json.dumps({
                "answer": "Total is 100",
                "citations": "S1"  # Not a list
            })
        )

        service = RAGAnswerService(gemini_client=mock_client)
        with pytest.raises(ValueError, match="Invalid citations in Gemini response"):
            await service.answer(
                question="What was the total?",
                context="Some context",
            )

    run_async(_run())


def test_rag_answer_service_invalid_citation_type_raises_value_error():
    async def _run():
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value=json.dumps({
                "answer": "Total is 100",
                "citations": [123]  # Items not strings
            })
        )

        service = RAGAnswerService(gemini_client=mock_client)
        with pytest.raises(ValueError, match="Invalid citation identifier"):
            await service.answer(
                question="What was the total?",
                context="Some context",
            )

    run_async(_run())


def test_rag_system_prompt_rules_present():
    assert "You are DocuMind AI, a document question-answering assistant." in RAG_SYSTEM_PROMPT
    assert "Cite supporting evidence using the supplied source IDs" in RAG_SYSTEM_PROMPT
    assert '"answer": "string"' in RAG_SYSTEM_PROMPT
    assert '"citations": ["S1"]' in RAG_SYSTEM_PROMPT
