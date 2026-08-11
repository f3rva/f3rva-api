"""Self-Service Member Alias Requests Router."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import AliasClaimRequest, AliasRequestResponse, ErrorResponse
from src.services.alias_service import AliasService

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/request",
    response_model=AliasRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit member alias claim request",
    description="Submits a request to link an alias name / duplicate member record to a primary member for admin review.",
    responses={
        201: {"description": "Alias request submitted successfully."},
        400: {"model": ErrorResponse, "description": "Invalid member IDs provided."},
        404: {"model": ErrorResponse, "description": "Primary or alias member not found."},
        409: {"model": ErrorResponse, "description": "Pending alias request already exists."},
    },
)
def request_alias(
    db: DbSession,
    payload: AliasClaimRequest,
) -> AliasRequestResponse:
    """Submit a self-service alias claim request."""
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
