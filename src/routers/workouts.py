"""Workouts & Backblasts REST API Router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import (
    AddWorkoutRequest,
    DeleteWorkoutResponse,
    ErrorResponse,
    UpdateWorkoutRequest,
    WorkoutCreatedResponse,
    WorkoutResponse,
    WorkoutUpdatedResponse,
)
from src.services.workout_mutation_service import WorkoutMutationService
from src.services.workout_service import WorkoutService
from src.utils.security import get_current_admin

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
    },
)
def get_recent_workouts(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    results: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
) -> list[WorkoutResponse]:
    """Retrieve recent workouts ordered by date descending."""
    workouts = WorkoutService.get_recent_workouts(db=db, page=page, page_size=results)
    if not workouts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 1001, "errorMessage": "Workout not found"},
        )
    return workouts


@router.post(
    "",
    response_model=WorkoutCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workout with data",
    description="Creates a new workout directly from structured payload data (title, workoutDate, qic, pax, aos, body, url, author, slug).",
    responses={
        201: {"description": "Workout created successfully."},
        400: {"model": ErrorResponse, "description": "Invalid input, missing required fields, or future workout date."},
    },
)
def add_workout(
    db: DbSession,
    payload: AddWorkoutRequest,
) -> WorkoutCreatedResponse:
    """Add a new workout directly with structured payload data."""
    return WorkoutMutationService.add_workout(db=db, data=payload)


@router.get(
    "/by-date",
    response_model=list[WorkoutResponse],
    summary="Get workouts by date components",
    description="Filter workouts by year, year+month, or exact day.",
    responses={
        200: {"description": "Filtered workouts list."},
        400: {"model": ErrorResponse, "description": "Invalid date parameter combination."},
        404: {"model": ErrorResponse, "description": "No workouts found for date."},
    },
)
def get_workouts_by_date(
    db: DbSession,
    year: Annotated[int, Query(ge=2010, le=2050, description="4-digit year")],
    month: Annotated[int | None, Query(ge=1, le=12, description="Month (1-12)")] = None,
    day: Annotated[int | None, Query(ge=1, le=31, description="Day of month (1-31)")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    results: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
) -> list[WorkoutResponse]:
    """Filter workouts by year, month, or exact day."""
    if day is not None and month is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errorCode": 1002,
                "errorMessage": "Month parameter is required when specifying day.",
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
    summary="Get workout by exact date and URL slug",
    description="Retrieves a single backblast matching the exact date and slug.",
    responses={
        200: {"description": "Workout found."},
        404: {"model": ErrorResponse, "description": "Workout not found."},
    },
)
def get_workout_by_date_and_slug(
    db: DbSession,
    year: Annotated[int, Query(ge=2010, le=2050, description="4-digit year")],
    month: Annotated[int, Query(ge=1, le=12, description="Month (1-12)")],
    day: Annotated[int, Query(ge=1, le=31, description="Day of month (1-31)")],
    slug: Annotated[str, Query(min_length=1, description="URL slug")],
) -> WorkoutResponse:
    """Retrieve workout by date and slug."""
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
    summary="Get workouts by AO ID or slug",
    description="Retrieves workouts associated with an Area of Operations (AO).",
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


@router.put(
    "/{workout_id}",
    response_model=WorkoutUpdatedResponse,
    status_code=status.HTTP_200_OK,
    summary="Update/refresh workout by ID",
    description="Updates an existing workout and replaces its details, AOs, Qs, and PAX attendees.",
    responses={
        200: {"description": "Workout updated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid input, missing required fields, or future workout date."},
        404: {"model": ErrorResponse, "description": "Workout not found."},
    },
)
def update_workout(
    db: DbSession,
    workout_id: int,
    payload: UpdateWorkoutRequest,
) -> WorkoutUpdatedResponse:
    """Update/refresh an existing workout by ID."""
    return WorkoutMutationService.update_workout(db=db, workout_id=workout_id, data=payload)


@router.delete(
    "/{workout_id}",
    response_model=DeleteWorkoutResponse,
    summary="Delete workout by ID (Admin)",
    description="Deletes a workout and all associated attendee, leader, AO, and detail records (Requires Bearer Token).",
    responses={
        200: {"description": "Workout deleted successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        404: {"model": ErrorResponse, "description": "Workout not found."},
    },
)
def delete_workout(
    db: DbSession,
    workout_id: int,
    current_admin: Annotated[str, Depends(get_current_admin)],
) -> DeleteWorkoutResponse:
    """Delete a workout and its attendee records (Admin only)."""
    return WorkoutMutationService.delete_workout(db=db, workout_id=workout_id)
