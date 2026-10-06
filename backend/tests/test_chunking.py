import pytest

from app.services.chunking_service import chunk_text


def test_chunking():
    text = "A" * 1200

    chunks = chunk_text(
        text=text,
        document_id="123",
        page=1,
        chunk_size=500,
        overlap=50,
    )

    assert len(chunks) == 3

    assert chunks[0]["chunk_id"] == "123_0"
    assert chunks[1]["chunk_id"] == "123_1"
    assert chunks[2]["chunk_id"] == "123_2"

    assert chunks[0]["page"] == 1

    assert len(chunks[0]["text"]) == 500
    assert len(chunks[1]["text"]) == 500
    assert len(chunks[2]["text"]) == 300


def test_empty_text():
    chunks = chunk_text(
        text="",
        document_id="123",
    )
    assert chunks == []


def test_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text(
            text="hello",
            document_id="123",
            chunk_size=100,
            overlap=100,
        )
