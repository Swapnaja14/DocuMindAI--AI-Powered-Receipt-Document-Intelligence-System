from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from app.core.database import users_collection
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import UserRole
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserCreate):
    email = user_data.email.lower()
    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    now = datetime.now(timezone.utc)

    user = {
        "email": email,
        "password_hash": hash_password(user_data.password),
        "role": UserRole.USER.value,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = users_collection.insert_one(user)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    return UserResponse(
        id=str(result.inserted_id),
        email=email,
        role=UserRole.USER,
        created_at=now,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(credentials: LoginRequest):
    email = credentials.email.lower()
    user = users_collection.find_one({"email": email})

    if not user or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user["_id"]))

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )