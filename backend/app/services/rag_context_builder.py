import re
from typing import Any, Dict, List, Tuple


def build_context(
    retrieved_chunks: List[Dict[str, Any]],
    max_chars_per_chunk: int = 4000,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Format retrieved chunks into a numbered evidence block suitable for LLM grounding.
    Assigns each piece of evidence a stable label: [S1], [S2], etc.

    Returns:
        (formatted_context_str, sources_metadata_list)
    """
    context_parts: List[str] = []
    sources: List[Dict[str, Any]] = []

    for index, chunk in enumerate(retrieved_chunks, start=1):
        source_id = f"S{index}"

        raw_text = chunk.get("text", "")
        truncated_text = raw_text[:max_chars_per_chunk].strip()

        filename = chunk.get("filename", "unknown.pdf")
        doc_id = str(chunk.get("document_id", ""))
        chunk_id = str(chunk.get("chunk_id", ""))
        page_val = chunk.get("page")
        page_display = str(page_val) if page_val is not None else "Unknown"

        extra_meta = ""
        meta_items = []
        if chunk.get("extracted_total") is not None:
            curr = chunk.get("extracted_currency") or ""
            meta_items.append(f"Receipt Total: {curr} {chunk.get('extracted_total')}".strip())
        if chunk.get("extracted_vendor"):
            meta_items.append(f"Vendor: {chunk.get('extracted_vendor')}")
        if chunk.get("extracted_date"):
            meta_items.append(f"Date: {chunk.get('extracted_date')}")
        if meta_items:
            extra_meta = "\n" + "\n".join(meta_items)

        context_entry = f"""
[{source_id}]
Filename: {filename}
Document ID: {doc_id}
Page: {page_display}
Chunk ID: {chunk_id}{extra_meta}
Evidence:
{truncated_text}
""".strip()

        context_parts.append(context_entry)

        sources.append({
            "source_id": source_id,
            "document_id": doc_id,
            "filename": filename,
            "page": page_val,
            "chunk_id": chunk_id,
            "snippet": truncated_text[:300].strip(),
            "score": chunk.get("score"),
        })

    formatted_context = "\n\n---\n\n".join(context_parts)
    return formatted_context, sources


def extract_cited_sources(
    answer: str,
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Parses citation markers like [S1], [S2], [S1, S2] from the LLM answer
    and matches them against the provided source list.
    If no explicit markers are found, returns all provided sources.
    """
    if not answer or not sources:
        return sources

    # Match patterns like [S1], [S2], [S10], etc.
    cited_ids = set(re.findall(r"\[S(\d+)\]", answer))
    if not cited_ids:
        # Fallback to returning all retrieved sources if LLM didn't use bracket citations
        return sources

    cited_source_labels = {f"S{num}" for num in cited_ids}
    filtered_sources = [
        s for s in sources if s.get("source_id") in cited_source_labels
    ]

    return filtered_sources if filtered_sources else sources
