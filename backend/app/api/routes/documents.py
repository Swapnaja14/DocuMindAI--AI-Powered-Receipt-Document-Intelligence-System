import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    status,
)

from app.api.routes.users import get_current_user
from app.core.config import settings
from app.core.database import db, documents_collection
from celery import chain
from app.models.document import DocumentStatus
from app.schemas.document import DocumentResponse, DocumentListItem, ChunkResponse
from app.repositories.chunk_repository import ChunkRepository
from app.services.cache_service import invalidate_user_cache
from app.tasks.document_tasks import process_ocr, extract_document, process_document
from app.tasks.chunking_tasks import chunk_document

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}

MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
):
    # 1. Validate File Type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. "
                "Allowed types: PDF, PNG, JPG, JPEG."
            ),
        )

    # 2. Read File
    contents = await file.read()

    # 3. Validate File Size
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the maximum allowed size "
                f"of {settings.max_file_size_mb} MB."
            ),
        )

    # 4. Generate unique storage filename
    extension = ALLOWED_FILE_TYPES[file.content_type]
    unique_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_directory = Path(settings.upload_dir)
    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = upload_directory / unique_filename

    # 5. Save file
    try:
        with open(file_path, "wb") as output_file:
            output_file.write(contents)

        # 6. Create MongoDB Document
        now = datetime.now(timezone.utc)

        document = {
            "user_id": current_user["_id"],
            "filename": file.filename or unique_filename,
            "file_type": extension,
            "file_path": str(file_path),
            "file_size": file_size,
            "status": DocumentStatus.UPLOADED.value,
            "ocr_status": "PENDING",
            "extraction_status": "PENDING",
            "chunking_status": "PENDING",
            "vector_status": "PENDING",
            "chunk_count": 0,
            "ocr": {
                "raw_text": "",
                "page_count": 0,
            },
            "extracted_data": {},
            "processing": {
                "uploaded_at": now,
                "processed_at": None,
                "processing_time_ms": None,
                "stage": "uploaded",
                "error": None,
            },
        }

        result = documents_collection.insert_one(document)

        document_id = str(result.inserted_id)

        try:
            chain(
                process_ocr.s(document_id),
                extract_document.s(),
                chunk_document.s(),
            ).apply_async()
        except Exception:
            documents_collection.update_one(
                {"_id": result.inserted_id},
                {
                    "$set": {
                        "status":  DocumentStatus.FAILED.value,
                    }
                },
            )
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = "Document was saved but could not be queued for processing.",
            )

    except Exception:
        # Remove saved file if MongoDB insertion fails
        if file_path.exists():
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document.",
        )

    # 7. Return response
    return DocumentResponse(
        id=str(result.inserted_id),
        user_id=str(current_user["_id"]),
        filename=document["filename"],
        file_type=document["file_type"],
        file_path=document["file_path"],
        file_size=document["file_size"],
        status=DocumentStatus.UPLOADED,
        ocr_status=document["ocr_status"],
        extraction_status=document["extraction_status"],
        chunking_status=document["chunking_status"],
        chunk_count=document["chunk_count"],
        ocr=document["ocr"],
        extracted_data=document["extracted_data"],
        chunks=document.get("chunks"),
        processing=document["processing"],
    )

@router.get(
    "",
    response_model=list[DocumentListItem],
)
def list_documents(
    current_user=Depends(get_current_user),
):
    documents = documents_collection.find(
        {
            "user_id": current_user["_id"],
        }
    ).sort( 
        "processing.uploaded_at", # upload timestamp
        -1, # descending (newest first)
    )

    return [
        DocumentListItem(
            id=str(document["_id"]),
            filename=document["filename"],
            file_type=document["file_type"],
            file_size=document["file_size"],
            status=document["status"],
            vector_status=document.get("vector_status", "PENDING"),
            uploaded_at=document["processing"]["uploaded_at"],
        )
        for document in documents
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: str,
    current_user=Depends(get_current_user),
):
    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID.",
        )

    document = documents_collection.find_one(
        {
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"],
        }
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return DocumentResponse(
        id=str(document["_id"]),
        user_id=str(document["user_id"]),
        filename=document["filename"],
        file_type=document["file_type"],
        file_path=document["file_path"],
        file_size=document["file_size"],
        status=document["status"],
        ocr_status=document.get("ocr_status", "PENDING"),
        extraction_status=document.get("extraction_status", "PENDING"),
        chunking_status=document.get("chunking_status", "PENDING"),
        vector_status=document.get("vector_status", "PENDING"),
        chunk_count=document.get("chunk_count", 0),
        ocr=document["ocr"],
        extracted_data=document["extracted_data"],
        chunks=document.get("chunks"),
        processing=document["processing"],
    )


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkResponse],
)
def get_document_chunks(
    document_id: str,
    current_user=Depends(get_current_user),
):
    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID.",
        )

    document = documents_collection.find_one(
        {
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"],
        }
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunk_repo = ChunkRepository(db)
    chunks = chunk_repo.get_document_chunks(document_id)

    return [
        ChunkResponse(
            chunk_id=c["chunk_id"],
            document_id=str(c["document_id"]),
            page=c["page"],
            text=c["text"],
            created_at=c.get("created_at"),
        )
        for c in chunks
    ]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    current_user=Depends(get_current_user)
):
    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID.",
        )

    document = documents_collection.find_one(
        {
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"],
        }
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    # Delete physical file
    file_path = Path(document["file_path"])

    if file_path.exists():
        try:
            file_path.unlink()
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {exc}",
            )

    # Delete chunks from document_chunks collection
    chunk_repo = ChunkRepository(db)
    chunk_repo.delete_document_chunks(document_id)

    # Delete MongoDB metadata
    documents_collection.delete_one(
        {
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"],
        }
    )

    # Invalidate user RAG cache
    user_id = (
        str(current_user.id)
        if hasattr(current_user, "id")
        else str(current_user.get("_id") or current_user.get("id"))
    )
    await invalidate_user_cache(user_id)