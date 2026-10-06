from typing import List, Dict

def chunk_text(
    text: str,
    document_id: str,
    page: int = 1,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[Dict]:

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()

    chunks = []
    start = 0
    chunk_index = 0

    step = chunk_size - overlap

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk = text[start:end].strip()

        if chunk:
            chunks.append({
                "document_id": str(document_id),
                "chunk_id": f"{document_id}_{chunk_index}",
                "page": page,
                "text": chunk,
            })

            chunk_index += 1
        start += step
    return chunks


def chunk_pages(
    pages: List[Dict],
    document_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[Dict]:

    all_chunks = []

    global_chunk_index = 0

    for page_data in pages:
        page_number = page_data["page"]
        text = page_data.get("text", "")

        page_chunks = chunk_text(
            text = text,
            document_id= document_id,
            page = page_number,
            chunk_size=chunk_size,
            overlap=overlap
        )

        for chunk in page_chunks:
            # Give every chunk a globally unique ID
            chunk["chunk_id"] = f"{document_id}_{global_chunk_index}"

            all_chunks.append(chunk)

            global_chunk_index += 1

    return all_chunks