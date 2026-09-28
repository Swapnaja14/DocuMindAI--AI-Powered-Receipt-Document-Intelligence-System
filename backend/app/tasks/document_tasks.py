import time
from datetime import datetime, timezone

from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import documents_collection
from app.models.document import DocumentStatus
from app.services.ocr_service import (
    ocr_document,
    OCRProcessingError,
)


@celery_app.task(
    name="process_document",
)
def process_document(document_id: str):
    """
    Asynchronously process an uploaded document.

    Current pipeline:
        File validation
            ↓
        PDF → images (if necessary)
            ↓
        OCR
            ↓
        Persist raw OCR text

    Future phases:
        OCR
            ↓
        Structured extraction
            ↓
        Chunking
            ↓
        Embeddings
            ↓
        FAISS
    """

    start_time = time.perf_counter()

    # ---------------------------------------------------------
    # 1. Validate document ID
    # ---------------------------------------------------------

    if not ObjectId.is_valid(document_id):
        raise ValueError(
            f"Invalid document ID: {document_id}"
        )

    object_id = ObjectId(document_id)

    # ---------------------------------------------------------
    # 2. Find document
    # ---------------------------------------------------------

    document = documents_collection.find_one(
        {"_id": object_id}
    )

    if not document:
        raise ValueError(
            f"Document not found: {document_id}"
        )

    # ---------------------------------------------------------
    # 3. Mark document as PROCESSING
    # ---------------------------------------------------------

    documents_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": DocumentStatus.PROCESSING.value,
                "processing.stage": "ocr_processing",
                "processing.error": None,
            }
        },
    )

    try:
        # =====================================================
        # PHASE 4 — OCR PIPELINE
        # =====================================================

        # -----------------------------------------------------
        # 4. Get uploaded file path
        # -----------------------------------------------------

        file_path = document.get("file_path")

        if not file_path:
            raise OCRProcessingError(
                "Document does not contain a file path."
            )

        # -----------------------------------------------------
        # 5. Run OCR
        #
        # For images:
        #     image → OCR → text
        #
        # For PDFs:
        #     PDF → page images → OCR → text
        # -----------------------------------------------------

        ocr_result = ocr_document(file_path)

        raw_text = ocr_result["raw_text"]
        page_count = ocr_result["page_count"]

        # -----------------------------------------------------
        # 6. Validate OCR output
        # -----------------------------------------------------

        if not raw_text.strip():
            raise OCRProcessingError(
                "OCR completed successfully, but no text "
                "was detected in the document."
            )

        # -----------------------------------------------------
        # 7. Persist raw OCR data
        # -----------------------------------------------------

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "ocr.raw_text": raw_text,
                    "ocr.page_count": page_count,
                    "processing.stage": "ocr_completed",
                }
            },
        )

        # =====================================================
        # PHASE 4 COMPLETE
        # =====================================================

        processing_time_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        now = datetime.now(timezone.utc)

        # -----------------------------------------------------
        # 8. Mark document as COMPLETED
        #
        # At this phase, COMPLETED means OCR processing
        # has successfully finished.
        #
        # Later phases will extend this pipeline.
        # -----------------------------------------------------

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.COMPLETED.value,
                    "processing.processed_at": now,
                    "processing.processing_time_ms": (
                        processing_time_ms
                    ),
                    "processing.stage": "ocr_completed",
                }
            },
        )

        return {
            "document_id": document_id,
            "status": DocumentStatus.COMPLETED.value,
            "processing_time_ms": processing_time_ms,
            "ocr_text_length": len(raw_text),
            "page_count": page_count,
        }

    except Exception as exc:
        # -----------------------------------------------------
        # 9. Mark document as FAILED
        # -----------------------------------------------------

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
                    "processing.stage": "failed",
                    "processing.error": str(exc),
                }
            },
        )

        raise