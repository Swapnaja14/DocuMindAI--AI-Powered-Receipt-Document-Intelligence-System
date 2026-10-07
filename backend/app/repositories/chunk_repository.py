from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


class ChunkRepository:
    def __init__(self, db):
        self.collection = db["document_chunks"]

    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return
        documents = []

        for chunk in chunks:
            documents.append({
                **chunk,
                "created_at": datetime.now(timezone.utc),
            })

        self.collection.insert_many(documents)

    def delete_document_chunks(self, document_id: str) -> None:
        self.collection.delete_many({
            "document_id": str(document_id)
        })

    def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        return list(
            self.collection.find(
                {"document_id": str(document_id)}
            ).sort("chunk_id", 1)
        )

    def get_chunk(
        self, document_id: str, chunk_id: Union[str, int]
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by document_id and chunk_id."""
        return self.collection.find_one({
            "document_id": str(document_id),
            "chunk_id": chunk_id,
        })