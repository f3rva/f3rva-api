"""Workouts & Backblasts REST API Router."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import ErrorResponse, WorkoutResponse
from src.services.workout_service import WorkoutService

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[WorkoutResponse],
    summary="Get recent workouts (Paginated)",
    description="Retrieves a paginated list of recent workouts ordered by workout date descending.",
    responses={
        200: {"description": "List of workouts retrieved successfully."},
        404: {"model": ErrorResponse, "description": "No workouts found."},
        400: {"model": ErrorResponse, "description": "Invalid page or results per page."},
    },
)
def get_workouts(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = 1,
    results: Annotated[int, Query(ge=1, le=100, description="Results per page (1-100)")] = 20,
) -> list[WorkoutResponse]:
    """Retrieve paginated recent workout backblasts."""
    workouts = WorkoutService.get_recent_workouts(db=db, page=page, page_size=results)
    if not workouts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workouts


@router.get(
    "/by-date",
    response_model=list[WorkoutResponse],
    summary="Get workouts by year, month, or day",
    description="Retrieves workouts filtered by year (all year), year+month, or exact year+month+day.",
    responses={
        200: {"description": "List of workouts retrieved successfully."},
        404: {"model": ErrorResponse, "description": "No workouts found matching date."},
        400: {"model": ErrorResponse, "description": "Invalid date parameters."},
    },
)
def get_workouts_by_date(
    db: DbSession,
    year: Annotated[int, Query(ge=2010, le=2050, description="4-digit Year (e.g. 2026)")],
    month: Annotated[int | None, Query(ge=1, le=12, description="Month (1-12)")] = None,
    day: Annotated[int | None, Query(ge=1, le=31, description="Day of month (1-31)")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    results: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
) -> list[WorkoutResponse]:
    """Retrieve workouts filtered by date components."""
    if day is not None and month is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errorCode": 1002,
                "errorMessage": "Invalid parameters. Day cannot be specified without a month.",
            },
        )

    workouts = WorkoutService.get_workouts_by_date(
        db=db, year=year, month=month, day=day, page=page, page_size=results
    )
    if not workouts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workouts


@router.get(
    "/by-date-slug",
    response_model=WorkoutResponse,
    summary="Get workout by exact date and post slug",
    description="Retrieves a specific workout backblast by year, month, day, and post slug.",
    responses={
        200: {"description": "Workout found."},
        404: {"model": ErrorResponse, "description": "Workout not found."},
        400: {"model": ErrorResponse, "description": "Invalid date or slug parameter."},
    },
)
def get_workout_by_date_slug(
    db: DbSession,
    year: Annotated[int, Query(ge=2010, le=2050, description="4-digit Year")],
    month: Annotated[int, Query(ge=1, le=12, description="Month (1-12)")],
    day: Annotated[int, Query(ge=1, le=31, description="Day (1-31)")],
    slug: Annotated[str, Query(min_length=1, description="Backblast URL slug")],
) -> WorkoutResponse:
    """Retrieve single workout by date and slug."""
    workout = WorkoutService.get_workout_by_date_and_slug(
        db=db, year=year, month=month, day=day, slug=slug
    )
    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workout


@router.get(
    "/ao/{ao_id_or_slug}",
    response_model=list[WorkoutResponse],
    summary="Get workouts by AO ID or AO slug",
    description="Retrieves paginated workouts for a specific Area of Operations (AO).",
    responses={
        200: {"description": "List of workouts for the specified AO."},
        404: {"model": ErrorResponse, "description": "No workouts found for this AO."},
    },
)
def get_workouts_by_ao(
    db: DbSession,
    ao_id_or_slug: str,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    results: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
) -> list[WorkoutResponse]:
    """Retrieve workouts associated with a specific AO ID or slug."""
    workouts = WorkoutService.get_workouts_by_ao(
        db=db, ao_identifier=ao_id_or_slug, page=page, page_size=results
    )
    if not workouts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workouts


@router.get(
    "/{workout_id}",
    response_model=WorkoutResponse,
    summary="Get workout detail by ID",
    description="Retrieves a single workout including Qs, AOs, and full PAX attendee roster.",
    responses={
        200: {"description": "Workout details found."},
        404: {"model": ErrorResponse, "description": "Workout not found."},
    },
)
def get_workout_by_id(
    db: DbSession,
    workout_id: int,
) -> WorkoutResponse:
    """Retrieve full workout detail by unique workout ID."""
    workout = WorkoutService.get_workout_by_id(db=db, workout_id=workout_id)
    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workout
