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
    jwt_secret = settings.jwt_secret_key
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": 5000, "errorMessage": "JWT secret key is not configured."},
        )
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.UTC) + (
        expires_delta or datetime.timedelta(hours=24)
    )
    to_encode.update({"exp": expire, "iat": datetime.datetime.now(datetime.UTC)})
    return jwt.encode(to_encode, jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT bearer token."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret_key
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": 5000, "errorMessage": "JWT secret key is not configured."},
        )
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


def has_admin_role(payload: dict[str, Any] | None) -> bool:
    """Return True if the decoded JWT payload contains the 'admin' role claim."""
    if not payload:
        return False
    if payload.get("role") == "admin":
        return True
    roles = payload.get("roles")
    return isinstance(roles, list) and "admin" in roles


def has_moderator_or_admin_role(payload: dict[str, Any] | None) -> bool:
    """Return True if the decoded JWT payload contains 'admin' or 'moderator' role claims."""
    if not payload:
        return False
    if payload.get("role") in ("admin", "moderator"):
        return True
    roles = payload.get("roles")
    return isinstance(roles, list) and ("admin" in roles or "moderator" in roles)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """FastAPI dependency to protect strictly admin-only endpoints (e.g., role management)."""
    payload = get_current_user(credentials)
    if not has_admin_role(payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": 4003, "errorMessage": "Admin role required."},
        )
    return payload


def get_current_moderator_or_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """FastAPI dependency to protect operational endpoints accessible to moderators and admins."""
    payload = get_current_user(credentials)
    if not has_moderator_or_admin_role(payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": 4003, "errorMessage": "Moderator or Admin role required."},
        )
    return payload

