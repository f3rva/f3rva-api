"""Analytical Reports, Leaderboards & AO Metrics REST API Router."""

from __future__ import annotations

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import (
    AOAttendanceSummary,
    AOLeaderboardResponse,
    AttendanceLeaderboardItem,
    DayOfWeekAttendance,
    ErrorResponse,
    MemberDistributionResponse,
)
from src.services.report_service import ReportService

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/attendance",
    response_model=list[AttendanceLeaderboardItem],
    summary="Member attendance leaderboard",
    description="Generates member attendance and Q leaderboard ranked by workout count, Q count, or Q-ratio within an optional date range.",
    responses={
        200: {"description": "Attendance leaderboard generated successfully."},
    },
)
def get_attendance_leaderboard(
    db: DbSession,
    start_date: Annotated[str | None, Query(alias="startDate", description="Filter start date YYYY-MM-DD")] = None,
    end_date: Annotated[str | None, Query(alias="endDate", description="Filter end date YYYY-MM-DD")] = None,
    sort_by: Annotated[
        Literal["workout", "q", "ratio"],
        Query(alias="sortBy", description="Ranking metric: workout (most workouts), q (most Qs), ratio (highest Q ratio)"),
    ] = "workout",
    limit: Annotated[int, Query(ge=1, le=500, description="Max leaderboard results to return")] = 50,
) -> list[AttendanceLeaderboardItem]:
    """Retrieve attendance leaderboard with flexible date filters and sorting options."""
    return ReportService.get_attendance_leaderboard(
        db=db,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        limit=limit,
    )


@router.get(
    "/ao",
    response_model=list[AOAttendanceSummary],
    summary="AO attendance metrics summary",
    description="Calculates total workouts conducted, total PAX attendance, and average PAX per workout across all AOs.",
    responses={
        200: {"description": "AO attendance summary calculated successfully."},
    },
)
def get_ao_attendance_summary(
    db: DbSession,
    start_date: Annotated[str | None, Query(alias="startDate", description="Filter start date YYYY-MM-DD")] = None,
    end_date: Annotated[str | None, Query(alias="endDate", description="Filter end date YYYY-MM-DD")] = None,
) -> list[AOAttendanceSummary]:
    """Retrieve AO-level aggregate attendance metrics and average attendance."""
    return ReportService.get_ao_attendance_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/ao/{ao_id}/leaderboard",
    response_model=AOLeaderboardResponse,
    summary="AO Leaderboard & Active Streakers",
    description="Retrieves top Qs, top attendees (PAX), and active consecutive attendance streaks for a specific AO.",
    responses={
        200: {"description": "AO leaderboard returned successfully."},
        404: {"model": ErrorResponse, "description": "AO not found."},
    },
)
def get_ao_leaderboard(
    db: DbSession,
    ao_id: int,
    limit: Annotated[int, Query(ge=1, le=100, description="Max entries per leaderboard category")] = 10,
) -> AOLeaderboardResponse:
    """Retrieve AO top leaders, top PAX, and active streakers."""
    leaderboard = ReportService.get_ao_leaderboard(db=db, ao_id=ao_id, limit=limit)
    if not leaderboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 3001, "errorMessage": f"AO with ID {ao_id} not found."},
        )
    return leaderboard


@router.get(
    "/day-of-week",
    response_model=list[DayOfWeekAttendance],
    summary="Day-of-week attendance distribution",
    description="Aggregates workout frequency, total attendance, and average attendance by day of the week (Sunday through Saturday).",
    responses={
        200: {"description": "Day-of-week attendance breakdown calculated successfully."},
    },
)
def get_day_of_week_attendance(
    db: DbSession,
    start_date: Annotated[str | None, Query(alias="startDate", description="Filter start date YYYY-MM-DD")] = None,
    end_date: Annotated[str | None, Query(alias="endDate", description="Filter end date YYYY-MM-DD")] = None,
) -> list[DayOfWeekAttendance]:
    """Retrieve workout statistics grouped by day of week."""
    return ReportService.get_day_of_week_attendance(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/members/{member_id}/distribution",
    response_model=MemberDistributionResponse,
    summary="Member AO attendance distribution",
    description="Calculates the breakdown of workouts attended and Q'd across every AO for a specific member.",
    responses={
        200: {"description": "Member AO distribution calculated successfully."},
        404: {"model": ErrorResponse, "description": "Member not found."},
    },
)
def get_member_distribution(
    db: DbSession,
    member_id: int,
) -> MemberDistributionResponse:
    """Retrieve AO attendance and Q distribution for a member."""
    distribution = ReportService.get_member_distribution(db=db, member_id=member_id)
    if not distribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 2001, "errorMessage": f"Member with ID {member_id} not found."},
        )
    return distribution
