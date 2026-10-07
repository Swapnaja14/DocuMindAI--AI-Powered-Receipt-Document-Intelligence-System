from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


class VectorMappingRepository:
    """
    Repository for managing the mapping between FAISS vector IDs
    and document chunks in MongoDB.
    """

    def __init__(self, db):
        self.collection = db["vector_mappings"]

    def insert_mappings(self, mappings: List[Dict[str, Any]]) -> None:
        """
        Insert vector mapping records.
        Each mapping dict should contain:
            - faiss_id (int)
            - document_id (str)
            - chunk_id (str or int)
        """
        if not mappings:
            return

        documents = [
            {
                "faiss_id": int(mapping["faiss_id"]),
                "document_id": str(mapping["document_id"]),
                "chunk_id": mapping["chunk_id"],
                "created_at": datetime.now(timezone.utc),
            }
            for mapping in mappings
        ]

        self.collection.insert_many(documents)

    def get_by_faiss_id(self, faiss_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a mapping record by FAISS vector ID."""
        return self.collection.find_one({"faiss_id": int(faiss_id)})

    def get_by_faiss_ids(self, faiss_ids: List[int]) -> List[Dict[str, Any]]:
        """Retrieve mapping records for a list of FAISS vector IDs."""
        if not faiss_ids:
            return []

        int_ids = [int(fid) for fid in faiss_ids]
        return list(self.collection.find({"faiss_id": {"$in": int_ids}}))

    def get_by_document_id(self, document_id: str) -> List[Dict[str, Any]]:
        """Retrieve all vector mappings for a specific document."""
        return list(
            self.collection.find({"document_id": str(document_id)}).sort("chunk_id", 1)
        )

    def delete_by_document_id(self, document_id: str) -> None:
        """Delete all vector mappings associated with a document."""
        self.collection.delete_many({"document_id": str(document_id)})
