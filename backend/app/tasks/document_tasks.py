import time
from datetime import datetime, timezone

from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import documents_collection
from app.models.document import DocumentStatus


@celery_app.task(
    name="process_document",
)
def process_document(document_id: str):
    """
    Asynchronously process a document.

    OCR, extraction, chunking, embeddings, and FAISS
    will be implemented in later phases.
    """

    start_time = time.perf_counter()

    # 1. Validate document ID
    if not ObjectId.is_valid(document_id):
        raise ValueError(
            f"Invalid document ID: {document_id}"
        )

    object_id = ObjectId(document_id)

    # 2. Find document
    document = documents_collection.find_one(
        {"_id": object_id}
    )

    if not document:
        raise ValueError(
            f"Document not found: {document_id}"
        )

    # 3. Mark document as PROCESSING
    documents_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": DocumentStatus.PROCESSING.value,
            }
        },
    )

    try:
        # -------------------------------------------------
        # FUTURE PROCESSING PIPELINE
        # -------------------------------------------------
        #
        # OCR
        # ↓
        # Extract fields
        # ↓
        # Chunk text
        # ↓
        # Generate embeddings
        # ↓
        # Update FAISS
        #
        # Implemented in later phases.
        # -------------------------------------------------

        # Temporary simulation
        time.sleep(2)

        processing_time_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        now = datetime.now(timezone.utc)

        # 4. Mark document as COMPLETED
        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.COMPLETED.value,
                    "processing.processed_at": now,
                    "processing.processing_time_ms": (
                        processing_time_ms
                    ),
                }
            },
        )

        return {
            "document_id": document_id,
            "status": DocumentStatus.COMPLETED.value,
            "processing_time_ms": processing_time_ms,
        }

    except Exception:
        # 5. Mark document as FAILED
        processing_time_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "processing.processing_time_ms": (
                        processing_time_ms
                    ),
                }
            },
        )

        raise