"""Workout Schedule REST API Router."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from src.models.schemas import ErrorResponse, WorkoutScheduleResponse
from src.services.schedule_service import ScheduleService

router = APIRouter()


@router.get(
    "",
    response_model=WorkoutScheduleResponse,
    summary="Get F3 RVA Workout Schedule",
    description="Retrieves active workout schedules transformed from the F3 Nation API with 15-minute public caching.",
    responses={
        200: {"description": "Active workout schedule returned successfully."},
        500: {"model": ErrorResponse, "description": "F3 Nation API Key not configured."},
        502: {"model": ErrorResponse, "description": "Upstream error connecting to F3 Nation API."},
    },
)
def get_workout_schedule(response: Response) -> WorkoutScheduleResponse:
    """Retrieve all active F3 RVA workouts from F3 Nation schedule API."""
    response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900"
    return ScheduleService.get_schedule()
