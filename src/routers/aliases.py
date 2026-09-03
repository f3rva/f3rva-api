"""Self-Service Member Alias Requests Router."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import AliasClaimRequest, AliasRequestResponse, ErrorResponse
from src.services.alias_service import AliasService
from src.utils.security import get_current_user

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.post(
    "/request",
    response_model=AliasRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit member alias claim request",
    description="Submits a request to link an alias name / duplicate member record to a primary member for admin review.",
    responses={
        201: {"description": "Alias request submitted successfully."},
        400: {"model": ErrorResponse, "description": "Invalid member IDs provided."},
        401: {"model": ErrorResponse, "description": "Authentication token missing or invalid."},
        403: {"model": ErrorResponse, "description": "Forbidden - can only claim aliases for own profile."},
        404: {"model": ErrorResponse, "description": "Primary or alias member not found."},
        409: {"model": ErrorResponse, "description": "Pending alias request already exists."},
    },
)
def request_alias(
    db: DbSession,
    payload: AliasClaimRequest,
    current_user: CurrentUser,
) -> AliasRequestResponse:
    """Submit a self-service alias claim request."""
    # Enforce that regular members can only claim aliases for their own profile
    role = current_user.get("role")
    if role != "admin":
        user_member_id = current_user.get("member_id")
        if user_member_id is None or int(payload.primary_member_id) != int(user_member_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "errorCode": 4003,
                    "errorMessage": "You can only submit alias claim requests for your own member profile.",
                },
            )

    return AliasService.request_alias(
        db=db,
        primary_id=payload.primary_member_id,
        alias_id=payload.alias_member_id,
    )


@router.get(
    "/requests",
    response_model=list[AliasRequestResponse],
    summary="Get pending alias requests (Public)",
    description="Retrieves all currently pending member alias requests to display on the self-service page.",
    responses={
        200: {"description": "List of pending alias requests."},
    },
)
def get_public_pending_alias_requests(
    db: DbSession,
) -> list[AliasRequestResponse]:
    """Retrieve public list of pending alias claim requests."""
    return AliasService.get_pending_requests(db=db)
