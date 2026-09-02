"""JWT Token Generation, Verification, and Admin Security Dependencies."""

from __future__ import annotations

import datetime
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.settings import get_settings

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict[str, Any], expires_delta: datetime.timedelta | None = None) -> str:
    """Generate a signed HS256 JWT bearer token."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret_key or "jwt-secret-key-fallback"
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.UTC) + (
        expires_delta or datetime.timedelta(hours=24)
    )
    to_encode.update({"exp": expire, "iat": datetime.datetime.now(datetime.UTC)})
    return jwt.encode(to_encode, jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT bearer token."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret_key or "jwt-secret-key-fallback"
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """FastAPI dependency to extract verified current authenticated user (member or admin)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Missing Bearer Authorization header."},
        )
    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Invalid token subject."},
        )
    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> str:
    """FastAPI dependency to protect admin endpoints using Bearer JWT authentication."""
    payload = get_current_user(credentials)
    username = payload.get("sub")
    role = payload.get("role")
    if role != "admin" and not username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": 4003, "errorMessage": "Admin role required."},
        )
    return str(username)
