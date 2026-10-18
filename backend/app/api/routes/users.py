from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import db, documents_collection, users_collection
from app.core.security import decode_access_token
from app.repositories.chunk_repository import ChunkRepository
from app.schemas.user import UserResponse
from app.services.cache_service import invalidate_user_cache

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        user_id = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID",
        )

    user = users_collection.find_one(
        {"_id": ObjectId(user_id)}
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        role=current_user["role"],
        created_at=current_user["created_at"],
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_me(current_user=Depends(get_current_user)):
    """
    Account Deletion Lifecycle:
    Permanently deletes user account, all owned receipts/documents, chunks,
    and associated cache entries.
    """
    user_id = current_user["_id"]
    str_user_id = str(user_id)

    # 1. Delete physical files and chunks
    user_docs = list(documents_collection.find({"user_id": user_id}))
    chunk_repo = ChunkRepository(db)
    for doc in user_docs:
        doc_id = str(doc["_id"])
        file_path_str = doc.get("file_path")
        if file_path_str:
            p = Path(file_path_str)
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        chunk_repo.delete_document_chunks(doc_id)

    # 2. Delete MongoDB documents
    documents_collection.delete_many({"user_id": user_id})

    # 3. Invalidate Redis cache
    try:
        await invalidate_user_cache(str_user_id)
    except Exception:
        pass

    # 4. Delete user record
    users_collection.delete_one({"_id": user_id})