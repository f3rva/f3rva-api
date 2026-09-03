"""Service layer integrating F3 Nation API events and transforming into F3 RVA Workout Schedule."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from fastapi import HTTPException, status

from src.config.settings import get_settings
from src.models.schemas import WorkoutScheduleItem, WorkoutScheduleResponse
from src.utils.logging import timed_service


def slugify(text: str) -> str:
    """Convert a string to a clean URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def transform_events_to_workouts(events: list[dict[str, Any]]) -> list[WorkoutScheduleItem]:
    """Transform raw F3 Nation API event objects into WorkoutScheduleItem instances."""
    workouts: list[WorkoutScheduleItem] = []
    for event in events:
        name = event.get("name", "")
        location_name = event.get("locationName") or event.get("locationAddress") or "TBD"

        # Build full address string for Google Maps search URL
        address_parts = [
            event.get("locationAddress"),
            event.get("locationCity"),
            event.get("locationState"),
            event.get("locationZip"),
        ]
        address_str = ", ".join(p for p in address_parts if p)
        if not address_str:
            address_str = location_name

        location_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(address_str)}"
        tag_url = f"/archives/ao/{slugify(name)}/"
        day_of_week = (event.get("dayOfWeek") or "").capitalize()

        # Extract workout style from eventTypes
        event_types = event.get("eventTypes") or []
        workout_style = event_types[0].get("eventTypeName", "") if event_types else ""

        # Extract siteQ if stored in metadata
        meta = event.get("meta") or {}
        site_q = meta.get("siteQ", "") if isinstance(meta, dict) else ""

        workouts.append(
            WorkoutScheduleItem(
                location=location_name,
                locationURL=location_url,
                name=name,
                tagURL=tag_url,
                dayOfWeek=day_of_week,
                startTime=event.get("startTime", "") or "",
                endTime=event.get("endTime", "") or "",
                workoutStyle=workout_style,
                siteQ=site_q,
                notes=event.get("description", "") or "",
            )
        )

    return workouts


class ScheduleService:
    """Service to fetch and format schedule data from upstream F3 Nation API."""

    @classmethod
    @timed_service
    def get_schedule(cls) -> WorkoutScheduleResponse:
        """Fetch active workout schedule from F3 Nation API and format for F3 RVA Website."""
        settings = get_settings()
        api_key = settings.f3_nation_api_key

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"errorCode": 5001, "errorMessage": "F3 Nation API Key is not configured."},
            )

        region_id = settings.f3_region_id or "25240"
        client_id = settings.client_id or "f3rva-website"
        api_url = (
            f"https://api.f3nation.com/v1/event?regionIds={region_id}&statuses=active&pageSize=200"
            f"&sorting[0][id]=dayOfWeek&sorting[0][desc]=&sorting[1][id]=parent&sorting[1][desc]="
        )

        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Client": client_id,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                events = data.get("events", [])
                workouts = transform_events_to_workouts(events)
                return WorkoutScheduleResponse(**{"1stF": workouts})
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"errorCode": 5002, "errorMessage": f"Failed to fetch schedule from F3 Nation API: {err}"},
            ) from err
