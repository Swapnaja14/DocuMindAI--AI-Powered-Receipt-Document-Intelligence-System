from typing import Any, Dict, List, Optional, Tuple
from app.schemas.rag import RAGAskResponse, RAGSource, RetrievalMetadata

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I could not find sufficient information in the retrieved documents to answer your question."
)

NEGATIVE_EVIDENCE_PHRASES = (
    "not available",
    "unavailable",
    "not found",
    "no information",
    "insufficient evidence",
    "insufficient information",
    "does not contain",
    "do not contain",
    "not mentioned",
    "no mention",
    "cannot find",
    "could not find",
    "no receipts",
    "no documents",
)


def validate_citations(
    model_citations: List[str],
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Validate model citations against the supplied source metadata.
    Filters out invalid/hallucinated source IDs and deduplicates in order of appearance.
    """
    source_map = {
        source["source_id"]: source
        for source in sources
        if "source_id" in source
    }

    validated: List[Dict[str, Any]] = []
    seen = set()

    for citation in model_citations:
        if not isinstance(citation, str):
            continue

        clean_id = citation.strip("[] ").upper()
        # Also check exact citation without uppercasing if exact match exists
        target_id = clean_id if clean_id in source_map else citation.strip("[] ")

        if target_id not in source_map:
            continue

        if target_id in seen:
            continue

        seen.add(target_id)
        validated.append(source_map[target_id])

    return validated


def is_insufficient_evidence_response(answer: str) -> bool:
    """
    Determine if the model's answer explicitly states that evidence is missing/unavailable.
    """
    if not answer:
        return True
    lower = answer.lower()
    return any(phrase in lower for phrase in NEGATIVE_EVIDENCE_PHRASES)


def resolve_grounded_answer(
    answer: str,
    model_citations: List[str],
    sources: List[Dict[str, Any]],
    fallback_message: str = INSUFFICIENT_EVIDENCE_MESSAGE,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Validates model citations and ensures answers are grounded.

    - If valid citations exist, returns (answer, validated_citations).
    - If no valid citations exist, but the answer already states evidence is unavailable,
      returns (answer, []).
    - If the model generates a substantive answer without any valid citations,
      rejects the ungrounded answer and returns (fallback_message, []).
    """
    validated = validate_citations(model_citations, sources)

    if validated:
        return answer, validated

    # No valid citations found
    if is_insufficient_evidence_response(answer):
        return answer, []

    # Substantive answer without valid evidence citations -> reject as ungrounded
    return fallback_message, []


def to_rag_sources(validated_sources: List[Dict[str, Any]]) -> List[RAGSource]:
    """
    Converts validated source dictionaries into validated RAGSource schema objects.
    """
    rag_sources: List[RAGSource] = []
    for s in validated_sources:
        rag_sources.append(
            RAGSource(
                document_id=str(s.get("document_id", "")),
                filename=str(s.get("filename", "unknown.pdf")),
                page=s.get("page"),
                chunk_id=str(s.get("chunk_id", "")),
                snippet=str(s.get("snippet", "")),
            )
        )
    return rag_sources


def build_rag_response(
    answer: str,
    model_citations: List[str],
    sources: List[Dict[str, Any]],
    top_k: int,
) -> RAGAskResponse:
    """
    Builds the final RAGAskResponse, ensuring citation validation and grounding checks.
    """
    final_answer, validated = resolve_grounded_answer(
        answer=answer,
        model_citations=model_citations,
        sources=sources,
    )
    rag_sources = to_rag_sources(validated)

    return RAGAskResponse(
        answer=final_answer,
        sources=rag_sources,
        retrieval=RetrievalMetadata(
            top_k=top_k,
            sources_used=len(rag_sources),
        ),
    )
