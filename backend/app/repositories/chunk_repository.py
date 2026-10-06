from datetime import datetime, timezone

class ChunkRepository:
    def __init__(self, db):
        self.collection = db["document_chunks"]

    def insert_chunks(self, chunks):
        if not chunks:
            return
        documents = []

        for chunk in chunks:
            documents.append({
                **chunk,
                "created_at": datetime.now(timezone.utc),
            })

        self.collection.insert_many(documents)

    def delete_document_chunks(self, document_id: str):
        self.collection.delete_many({
            "document_id": str(document_id)
        })

    def get_document_chunks(self, document_id: str):
        return list(
            self.collection.find(
                {"document_id": str(document_id)}
            ).sort("chunk_id", 1)
        )