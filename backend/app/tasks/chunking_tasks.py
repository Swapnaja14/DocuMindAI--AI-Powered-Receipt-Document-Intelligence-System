from datetime import datetime, timezone
from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import db
from app.models.document import DocumentStatus
from app.repositories.chunk_repository import ChunkRepository
from app.services.chunking_service import chunk_text


@celery_app.task(
    bind=True,
    name="chunk_document",
)
def chunk_document(self, document_id):
    """
    Chunk the OCR text of a processed document, persist chunks in document_chunks,
    update chunking status and count in MongoDB, and return document_id.
    """
    if isinstance(document_id, dict):
        document_id = document_id.get("document_id")
    else:
        document_id = str(document_id)

    if not ObjectId.is_valid(document_id):
        raise ValueError(f"Invalid document ID: {document_id}")

    object_id = ObjectId(document_id)
    document = db["documents"].find_one({"_id": object_id})

    if not document:
        raise ValueError(f"Document {document_id} not found")

    try:
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "chunking_status": "PROCESSING",
                    "processing.stage": "chunking_processing",
                }
            },
        )

        # 1. Retrieve raw OCR text
        raw_text = document.get("ocr", {}).get("raw_text", "")

        # 2. Chunk text
        chunks = chunk_text(
            text=raw_text,
            document_id=str(document_id),
        )

        # 3. Persist chunks in document_chunks collection
        chunk_repo = ChunkRepository(db)
        chunk_repo.delete_document_chunks(str(document_id))
        chunk_repo.insert_chunks(chunks)

        # 4. Update document's chunking_status, chunk_count, and status
        now = datetime.now(timezone.utc)
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "chunking_status": "COMPLETED",
                    "chunk_count": len(chunks),
                    "status": DocumentStatus.COMPLETED.value,
                    "processing.processed_at": now,
                    "processing.stage": "chunking_completed",
                },
                "$unset": {
                    "chunks": "",
                },
            },
        )

        return str(document_id)

    except Exception as exc:
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "chunking_status": "FAILED",
                    "processing.stage": "chunking_failed",
                    "processing.error": str(exc),
                }
            },
        )
        raise