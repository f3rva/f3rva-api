"""JWT Token Generation, Verification, and Admin Security Dependencies."""

from __future__ import annotations

import datetime
from typing import Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from src.config.settings import get_settings

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict[str, Any], expires_delta: datetime.timedelta | None = None) -> str:
    """Generate a signed HS256 JWT bearer token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta or datetime.timedelta(hours=24)
    )
    to_encode.update({"exp": expire, "iat": datetime.datetime.now(datetime.timezone.utc)})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT bearer token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4011, "errorMessage": "Token has expired."},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Invalid or malformed authentication token."},
        ) from None


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> str:
    """FastAPI dependency to protect admin endpoints using Bearer JWT authentication."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Missing Bearer Authorization header."},
        )
    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Invalid token subject."},
        )
    return str(username)
