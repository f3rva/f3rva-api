"""Members & PAX REST API Router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import (
    ErrorResponse,
    MemberDetailResponse,
    MemberStatsResponse,
    MemberSummary,
)
from src.services.member_service import MemberService

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[MemberSummary],
    summary="Get all members",
    description="Retrieves an alphabetical list of all registered F3 members and their member IDs.",
    responses={
        200: {"description": "Alphabetical list of all members."},
    },
)
def get_members(db: DbSession) -> list[MemberSummary]:
    """Retrieve all registered members ordered alphabetically."""
    return MemberService.get_all_members(db=db)


@router.get(
    "/lookup",
    response_model=list[MemberSummary],
    summary="Lookup member by name or alias",
    description="Case-insensitive search across primary F3 names and registered aliases.",
    responses={
        200: {"description": "List of matching members found."},
        404: {"model": ErrorResponse, "description": "No members found matching the search criteria."},
        400: {"model": ErrorResponse, "description": "Invalid search query parameter."},
    },
)
def lookup_member(
    db: DbSession,
    name: Annotated[str, Query(min_length=1, description="Search term for F3 name or alias")],
) -> list[MemberSummary]:
    """Lookup members matching name or alias."""
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": 2002, "errorMessage": "Search name parameter cannot be empty."},
        )

    results = MemberService.lookup_members(db=db, query_str=clean_name)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 2001, "errorMessage": f"No members found matching '{clean_name}'."},
        )
    return results


@router.get(
    "/{member_id}",
    response_model=MemberDetailResponse,
    summary="Get member profile and workout history",
    description="Retrieves a member profile with registered aliases, attendance stats, and attended & Q'd workout history.",
    responses={
        200: {"description": "Member profile found."},
        404: {"model": ErrorResponse, "description": "Member not found."},
    },
)
def get_member_by_id(
    db: DbSession,
    member_id: int,
) -> MemberDetailResponse:
    """Retrieve complete member profile by unique member ID."""
    member = MemberService.get_member_by_id(db=db, member_id=member_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 2001, "errorMessage": f"Member with ID {member_id} not found."},
        )
    return member


@router.get(
    "/{member_id}/stats",
    response_model=MemberStatsResponse,
    summary="Get member statistics",
    description="Calculates total workouts attended, total Qs led, and the calculated Q-ratio (Qs / Workouts).",
    responses={
        200: {"description": "Member stats calculated successfully."},
        404: {"model": ErrorResponse, "description": "Member not found."},
    },
)
def get_member_stats(
    db: DbSession,
    member_id: int,
) -> MemberStatsResponse:
    """Retrieve workout attendance statistics and Q-ratio for a member."""
    stats = MemberService.get_member_stats(db=db, member_id=member_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 2001, "errorMessage": f"Member with ID {member_id} not found."},
        )
    return stats
