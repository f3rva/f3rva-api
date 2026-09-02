"""Admin Operations & Protected Management REST API Router."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import get_settings
from src.models.schemas import (
    AdminLoginRequest,
    AliasClaimRequest,
    AliasRequestResponse,
    ErrorResponse,
    TokenResponse,
)
from src.services.alias_service import AliasService
from src.utils.security import create_access_token, get_current_admin

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Admin authentication",
    description="Validates admin credentials and issues a signed 24-hour JWT Bearer token for protected management operations.",
    responses={
        200: {"description": "Admin authenticated successfully."},
        401: {"model": ErrorResponse, "description": "Invalid username or password."},
    },
)
def admin_login(
    payload: AdminLoginRequest,
) -> TokenResponse:
    """Authenticate administrator and return signed JWT bearer token."""
    settings = get_settings()
    admin_user = settings.admin_username or ""
    admin_pass = settings.admin_password or ""
    username_valid = bool(admin_user) and hmac.compare_digest(payload.username, admin_user)
    password_valid = bool(admin_pass) and hmac.compare_digest(payload.password, admin_pass)

    if not (username_valid and password_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4001, "errorMessage": "Invalid username or password."},
        )

    token = create_access_token(data={"sub": payload.username, "role": "admin"})
    return TokenResponse(
        accessToken=token,
        tokenType="bearer",
        expiresIn=86400,
    )


@router.get(
    "/aliases/requests",
    response_model=list[AliasRequestResponse],
    summary="Get pending alias requests (Admin)",
    description="Retrieves all pending member alias requests awaiting administrator approval (Requires Bearer Token).",
    responses={
        200: {"description": "List of pending alias requests."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
    },
)
def get_pending_alias_requests(
    db: DbSession,
    current_admin: Annotated[str, Depends(get_current_admin)],
) -> list[AliasRequestResponse]:
    """Retrieve all pending alias requests."""
    return AliasService.get_pending_requests(db=db)


@router.post(
    "/aliases/approve/{primary_member_id}/{alias_member_id}",
    response_model=AliasRequestResponse,
    summary="Approve alias request (Admin)",
    description="Approves a member alias request, merges attendance records, updates aliases, and removes the duplicate member (Requires Bearer Token).",
    responses={
        200: {"description": "Alias approved and records merged successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        404: {"model": ErrorResponse, "description": "Alias request not found."},
    },
)
def approve_alias_request(
    db: DbSession,
    primary_member_id: int,
    alias_member_id: int,
    current_admin: Annotated[str, Depends(get_current_admin)],
) -> AliasRequestResponse:
    """Approve alias request and merge records."""
    return AliasService.approve_alias(
        db=db, primary_id=primary_member_id, alias_id=alias_member_id
    )


@router.post(
    "/aliases/reject/{primary_member_id}/{alias_member_id}",
    response_model=AliasRequestResponse,
    summary="Reject alias request (Admin)",
    description="Rejects a pending member alias request (Requires Bearer Token).",
    responses={
        200: {"description": "Alias request rejected successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        404: {"model": ErrorResponse, "description": "Alias request not found."},
    },
)
def reject_alias_request(
    db: DbSession,
    primary_member_id: int,
    alias_member_id: int,
    current_admin: Annotated[str, Depends(get_current_admin)],
) -> AliasRequestResponse:
    """Reject a pending alias request."""
    return AliasService.reject_alias(
        db=db, primary_id=primary_member_id, alias_id=alias_member_id
    )


@router.post(
    "/members/merge",
    response_model=AliasRequestResponse,
    summary="Directly merge two members (Admin)",
    description="Directly merges a duplicate member record into a primary member, creates audit trails, updates aliases, and reassigns attendance (Requires Bearer Token).",
    responses={
        200: {"description": "Members merged successfully."},
        400: {"model": ErrorResponse, "description": "Cannot merge identical members."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        404: {"model": ErrorResponse, "description": "One or more members not found."},
    },
)
def direct_merge_members(
    db: DbSession,
    payload: AliasClaimRequest,
    current_admin: Annotated[str, Depends(get_current_admin)],
) -> AliasRequestResponse:
    """Directly merge two member entities."""
    return AliasService.direct_merge(
        db=db,
        primary_id=payload.primary_member_id,
        alias_id=payload.alias_member_id,
    )
