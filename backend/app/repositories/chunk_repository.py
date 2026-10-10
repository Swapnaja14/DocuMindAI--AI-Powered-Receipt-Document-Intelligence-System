from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId


class ChunkRepository:
    def __init__(self, db):
        self.collection = db["document_chunks"]

    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Insert multiple chunks and return their inserted MongoDB string IDs.
        """
        if not chunks:
            return []
        documents = []

        for chunk in chunks:
            documents.append({
                **chunk,
                "created_at": datetime.now(timezone.utc),
            })

        result = self.collection.insert_many(documents)
        return [str(inserted_id) for inserted_id in result.inserted_ids]

    def create_chunk(self, chunk: Dict[str, Any]) -> str:
        """
        Insert a single chunk and return its inserted MongoDB string ID.
        """
        doc = {
            **chunk,
            "created_at": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def update_embedding(
        self, chunk_id: Union[str, ObjectId], embedding: List[float]
    ) -> None:
        """
        Update a chunk record with its generated embedding vector.
        """
        if isinstance(chunk_id, str) and ObjectId.is_valid(chunk_id):
            query = {"_id": ObjectId(chunk_id)}
        elif isinstance(chunk_id, ObjectId):
            query = {"_id": chunk_id}
        else:
            query = {"chunk_id": chunk_id}

        self.collection.update_one(
            query,
            {
                "$set": {
                    "embedding": embedding,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    def delete_chunk_by_id(self, chunk_id: Union[str, ObjectId]) -> int:
        """Delete a single chunk by chunk_id or ObjectId."""
        if isinstance(chunk_id, str) and ObjectId.is_valid(chunk_id):
            query = {"$or": [{"_id": ObjectId(chunk_id)}, {"chunk_id": chunk_id}]}
        elif isinstance(chunk_id, ObjectId):
            query = {"_id": chunk_id}
        else:
            query = {"chunk_id": chunk_id}
        res = self.collection.delete_one(query)
        return res.deleted_count

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

    def get_chunks_with_embeddings(self) -> List[Dict[str, Any]]:
        """
        Return all chunks that have valid embeddings.
        """
        return list(
            self.collection.find(
                {
                    "embedding": {
                        "$exists": True,
                        "$ne": None,
                    }
                },
                {
                    "_id": 1,
                    "chunk_id": 1,
                    "embedding": 1,
                },
            )
        )