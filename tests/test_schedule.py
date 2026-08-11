"""Unit and Integration Tests for F3 RVA Workout Schedule API."""

from __future__ import annotations

import json
import urllib.request

import pytest
from fastapi.testclient import TestClient

from src.config.settings import get_settings
from src.services.schedule_service import slugify, transform_events_to_workouts

MOCK_F3_NATION_RESPONSE = {
    "events": [
        {
            "name": "First Watch",
            "locationName": "Gaskins Park & Ride",
            "locationAddress": "9800 Mayland Dr",
            "locationCity": "Richmond",
            "locationState": "VA",
            "locationZip": "23233",
            "dayOfWeek": "monday",
            "startTime": "0530",
            "endTime": "0615",
            "eventTypes": [{"eventTypeName": "Bootcamp"}],
            "meta": {"siteQ": "Handshake"},
            "description": "Bring gloves and water.",
        },
        {
            "name": "Spider Run",
            "locationName": None,
            "locationAddress": "University of Richmond",
            "locationCity": "Richmond",
            "locationState": "VA",
            "locationZip": "23173",
            "dayOfWeek": "wednesday",
            "startTime": "0530",
            "endTime": "0615",
            "eventTypes": [{"eventTypeName": "Run"}],
            "meta": {},
            "description": "",
        },
    ]
}


class MockHTTPResponse:
    """Mock urllib response object."""

    def __init__(self, data: dict, status_code: int = 200) -> None:
        self.data = data
        self.status = status_code

    def read(self) -> bytes:
        return json.dumps(self.data).encode("utf-8")

    def __enter__(self) -> MockHTTPResponse:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def test_slugify() -> None:
    """Test URL slugification helper."""
    assert slugify("First Watch") == "first-watch"
    assert slugify("The  Dogpile -- RVA!") == "the-dogpile-rva"
    assert slugify("AO #42: Gridiron") == "ao-42-gridiron"


def test_transform_events_to_workouts() -> None:
    """Test transformation from F3 Nation raw events to WorkoutScheduleItem."""
    items = transform_events_to_workouts(MOCK_F3_NATION_RESPONSE["events"])
    assert len(items) == 2

    # First Watch assertion
    fw = items[0]
    assert fw.name == "First Watch"
    assert fw.location == "Gaskins Park & Ride"
    assert "9800+Mayland+Dr" in fw.location_url or "9800%20Mayland%20Dr" in fw.location_url
    assert fw.tag_url == "/archives/ao/first-watch/"
    assert fw.day_of_week == "Monday"
    assert fw.start_time == "0530"
    assert fw.end_time == "0615"
    assert fw.workout_style == "Bootcamp"
    assert fw.site_q == "Handshake"
    assert fw.notes == "Bring gloves and water."

    # Spider Run assertion
    sr = items[1]
    assert sr.name == "Spider Run"
    assert sr.location == "University of Richmond"
    assert sr.tag_url == "/archives/ao/spider-run/"
    assert sr.day_of_week == "Wednesday"
    assert sr.workout_style == "Run"
    assert sr.site_q == ""


def test_get_workout_schedule_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GET /schedule returns 200 with 1stF array and public cache headers."""
    settings = get_settings()
    monkeypatch.setattr(settings, "f3_nation_api_key", "test-api-key")

    def mock_urlopen(req, timeout=10):
        return MockHTTPResponse(MOCK_F3_NATION_RESPONSE)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    response = client.get("/schedule")
    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "public, max-age=900, s-maxage=900"
    data = response.json()
    assert "1stF" in data
    assert len(data["1stF"]) == 2
    assert data["1stF"][0]["name"] == "First Watch"


def test_get_workout_schedule_missing_api_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GET /schedule returns 500 when F3 Nation API key is missing."""
    settings = get_settings()
    monkeypatch.setattr(settings, "f3_nation_api_key", None)

    response = client.get("/schedule")
    assert response.status_code == 500
    data = response.json()
    assert data["errorCode"] == 5001


def test_get_workout_schedule_upstream_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GET /schedule returns 502 when upstream call throws an error."""
    settings = get_settings()
    monkeypatch.setattr(settings, "f3_nation_api_key", "test-api-key")

    def mock_urlopen_error(req, timeout=10):
        raise urllib.error.URLError("Upstream timeout")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_error)

    response = client.get("/schedule")
    assert response.status_code == 502
    data = response.json()
    assert data["errorCode"] == 5002
