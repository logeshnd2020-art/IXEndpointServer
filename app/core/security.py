from datetime import datetime, timedelta, timezone
import os
import uuid
from typing import Any, Dict, Optional, Union

from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import SECRET_KEY


# Password hashing / verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# JWT settings
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set in app.core.config")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = _now()
    if expires_delta is None:
        expires = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expires = now + expires_delta

    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": jti,
        "type": "access",
    }

    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def create_refresh_token(
    subject: Union[str, int], expires_delta: Optional[timedelta] = None
) -> str:
    now = _now()
    if expires_delta is None:
        expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expires = now + expires_delta

    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": jti,
        "type": "refresh",
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise
