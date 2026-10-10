from app.services.rag_context_builder import build_context, extract_cited_sources


def test_build_context_empty():
    context, sources = build_context([])
    assert context == ""
    assert sources == []


def test_build_context_multiple_chunks():
    chunks = [
        {
            "chunk_id": "c_101",
            "document_id": "doc_1",
            "filename": "apple_laptop.pdf",
            "page": 1,
            "text": "MacBook Pro 16-inch total: ₹1,99,000",
            "score": 0.88,
        },
        {
            "chunk_id": "c_102",
            "document_id": "doc_2",
            "filename": "dell_laptop.pdf",
            "page": 2,
            "text": "Dell XPS 15 total: ₹1,45,000",
            "score": 0.79,
        },
    ]

    context, sources = build_context(chunks)

    # Check context formatting
    assert "[S1]" in context
    assert "[S2]" in context
    assert "Filename: apple_laptop.pdf" in context
    assert "Document ID: doc_1" in context
    assert "Page: 1" in context
    assert "Chunk ID: c_101" in context
    assert "MacBook Pro 16-inch total: ₹1,99,000" in context

    assert "Filename: dell_laptop.pdf" in context
    assert "Page: 2" in context

    # Check sources list
    assert len(sources) == 2
    assert sources[0]["source_id"] == "S1"
    assert sources[0]["document_id"] == "doc_1"
    assert sources[0]["filename"] == "apple_laptop.pdf"
    assert sources[0]["chunk_id"] == "c_101"
    assert sources[0]["page"] == 1
    assert sources[0]["snippet"] == "MacBook Pro 16-inch total: ₹1,99,000"

    assert sources[1]["source_id"] == "S2"
    assert sources[1]["document_id"] == "doc_2"


def test_build_context_max_chars_truncation():
    long_text = "A" * 5000
    chunks = [
        {
            "chunk_id": "c_long",
            "document_id": "doc_x",
            "filename": "long.pdf",
            "page": 1,
            "text": long_text,
        }
    ]

    context, sources = build_context(chunks, max_chars_per_chunk=500)
    # Evidence should be truncated to 500 chars
    assert "A" * 500 in context
    assert "A" * 501 not in context
    # Snippet in sources metadata should be truncated to 300 chars
    assert len(sources[0]["snippet"]) == 300


def test_extract_cited_sources():
    sources = [
        {"source_id": "S1", "document_id": "doc_1", "filename": "doc1.pdf"},
        {"source_id": "S2", "document_id": "doc_2", "filename": "doc2.pdf"},
        {"source_id": "S3", "document_id": "doc_3", "filename": "doc3.pdf"},
    ]

    # LLM explicitly cites [S1] and [S3]
    answer = "The highest purchase was the laptop for ₹1,99,000 [S1], compared to ₹72,000 [S3]."
    cited = extract_cited_sources(answer, sources)
    assert len(cited) == 2
    assert {s["source_id"] for s in cited} == {"S1", "S3"}

    # Fallback if no citations in brackets
    answer_no_cites = "The highest purchase was ₹1,99,000."
    all_fallback = extract_cited_sources(answer_no_cites, sources)
    assert len(all_fallback) == 3
