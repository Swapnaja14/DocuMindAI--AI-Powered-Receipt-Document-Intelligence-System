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
from app.core.database import documents_collection
from app.models.document import DocumentStatus
from app.schemas.document import DocumentResponse, DocumentListItem

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
            "ocr": {
                "raw_text": "",
                "page_count": 0,
            },
            "extracted_data": {
                "vendor": None,
                "invoice_number": None,
                "date": None,
                "currency": None,
                "subtotal": None,
                "tax": None,
                "total": None,
            },
            "chunks": [],
            "processing": {
                "uploaded_at": now,
                "processed_at": None,
                "processing_time_ms": None,
            },
        }

        result = documents_collection.insert_one(document)

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
        ocr=document["ocr"],
        extracted_data=document["extracted_data"],
        chunks=document["chunks"],
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
            detail="Document not found",
        )

    return DocumentResponse(
        id=str(document["_id"]),
        user_id=str(document["user_id"]),
        filename=str(document["filename"]),
        file_type=document["file_type"],
        file_path=document["file_path"],
        file_size=document["file_size"],
        status=document["status"],
        ocr=document["ocr"],
        extracted_data=document["extracted_data"],
        chunks=document["chunks"],
        processing=document["processing"],
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
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

    # Delete MongoDB metadata
    documents_collection.delete_one(
        {
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"],
        }
    )