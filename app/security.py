from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import hmac
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# ----------------------------
# Password Hashing
# ----------------------------

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        from fastapi import HTTPException
        raise HTTPException(422, "Password must be at most 72 UTF-8 bytes")
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_refresh_token(
    plain_token: str,
    hashed_token: str,
) -> bool:
    return hmac.compare_digest(hash_refresh_token(plain_token), hashed_token)

# ----------------------------
# Access Token
# ----------------------------

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    )

    to_encode.update(
        {
            "exp": expire,
            "type": "access",
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


# ----------------------------
# Refresh Token
# ----------------------------

def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        )
    )

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": uuid.uuid4().hex,
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


# ----------------------------
# Decode Token
# ----------------------------

def decode_access_token(
    token: str,
) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "access":
            return None

        return payload

    except JWTError:
        return None


def decode_refresh_token(
    token: str,
) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "refresh":
            return None

        return payload

    except JWTError:
        return None
