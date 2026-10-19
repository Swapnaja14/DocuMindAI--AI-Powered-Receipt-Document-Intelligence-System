from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError

from app.core.config import settings

_hasher = PasswordHasher()


class _PasswordHashWrapper:
    """Compatibility wrapper providing .hash() and .verify() interface."""

    def hash(self, password: str) -> str:
        return _hasher.hash(password)

    def verify(self, password: str, hashed_password: str) -> bool:
        try:
            return _hasher.verify(hashed_password, password)
        except (VerificationError, InvalidHash):
            return False
        except Exception:
            return False


password_hash = _PasswordHashWrapper()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHash):
        return False
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    user_id = payload.get("sub")

    if not user_id:
        raise ValueError("Invalid Token")

    return user_id
