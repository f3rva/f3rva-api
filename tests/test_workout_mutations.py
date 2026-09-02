"""Unit and Integration Tests for Structured Workout Additions and Protected Deletions."""

from __future__ import annotations

import datetime

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.workout import AO, Workout, WorkoutAO, WorkoutDetails, WorkoutPax, WorkoutQ
from src.utils.security import create_access_token


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Generate default test bearer auth headers for Dingo."""
    token = create_access_token(data={"sub": "U12345", "member_id": 1, "f3_name": "Dingo", "role": "member"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Generate admin test bearer auth headers."""
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_slack_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no live Slack notifications are ever dispatched during workout mutation tests."""
    monkeypatch.setattr(
        "src.services.workout_mutation_service.SlackNotificationService.post_backblast_summary",
        lambda *args, **kwargs: True,
    )


def test_add_workout_with_aos_objects(client: TestClient, db_session: Session, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts creates workout with structured AO objects (name and slug)."""
    payload = {
        "title": "Beatdown at First Watch",
        "workoutDate": "2026-08-07",
        "qic": "Dingo, Lab Rat",
        "pax": "Dingo, Lab Rat, Splinter, Swag",
        "aos": [
            {"name": "First Watch", "slug": "first-watch"},
            {"name": "Spider Run", "slug": "spider-run"},
        ],
        "body": "<p>100 burpees and 5 miles.</p>",
        "url": "https://f3rva.org/2026/08/07/beatdown-at-first-watch",
        "author": "Dingo",
        "slug": "beatdown-at-first-watch",
    }
    response = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    workout_id = data["id"]

    # Verify persisted records in DB
    w = db_session.query(Workout).filter(Workout.workout_id == workout_id).first()
    assert w is not None
    assert w.title == "Beatdown at First Watch"
    assert w.workout_date == datetime.date(2026, 8, 7)

    # Details
    det = db_session.query(WorkoutDetails).filter(WorkoutDetails.workout_id == workout_id).first()
    assert det is not None
    assert det.html_content == "<p>100 burpees and 5 miles.</p>"

    # Qs (2)
    qs = db_session.query(WorkoutQ).filter(WorkoutQ.workout_id == workout_id).all()
    assert len(qs) == 2

    # PAX (4)
    pax = db_session.query(WorkoutPax).filter(WorkoutPax.workout_id == workout_id).all()
    assert len(pax) == 4

    # AOs (2) and verify slug was persisted
    aos = db_session.query(WorkoutAO).filter(WorkoutAO.workout_id == workout_id).all()
    assert len(aos) == 2

    first_watch = db_session.query(AO).filter(AO.description == "First Watch").first()
    assert first_watch is not None
    assert first_watch.slug == "first-watch"


def test_add_workout_with_list_inputs(client: TestClient, db_session: Session, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts creates workout when Qs, PAX are lists and AO has auto-derived slug."""
    payload = {
        "title": "Dogpile Ruck",
        "workoutDate": "20260805",
        "qic": ["Splinter"],
        "pax": ["Splinter", "Lab Rat"],
        "aos": [{"name": "Dogpile"}],
    }
    response = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    workout_id = data["id"]

    w = db_session.query(Workout).filter(Workout.workout_id == workout_id).first()
    assert w is not None
    assert w.workout_date == datetime.date(2026, 8, 5)

    aos = db_session.query(WorkoutAO).filter(WorkoutAO.workout_id == workout_id).all()
    assert len(aos) == 1

    dogpile = db_session.query(AO).filter(AO.description == "Dogpile").first()
    assert dogpile is not None
    assert dogpile.slug == "dogpile"


def test_add_workout_date_formats(client: TestClient, db_session: Session, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts accepts varied valid date strings."""
    for date_str, expected in [
        ("08/07/2026", datetime.date(2026, 8, 7)),
        ("August 7, 2026", datetime.date(2026, 8, 7)),
    ]:
        payload = {
            "title": "Format Test",
            "workoutDate": date_str,
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "Gridiron", "slug": "gridiron"}],
        }
        res = client.post("/v2/workouts", json=payload, headers=auth_headers)
        assert res.status_code == 201
        w = db_session.query(Workout).filter(Workout.workout_id == res.json()["id"]).first()
        assert w is not None
        assert w.workout_date == expected


def test_add_workout_invalid_date_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts rejects invalid date format with 400."""
    payload = {
        "title": "Invalid Date Test",
        "workoutDate": "NotADate",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert res.status_code == 400
    assert res.json()["errorCode"] == 1002


def test_add_workout_future_date_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts rejects future date with 400."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    payload = {
        "title": "Future Test",
        "workoutDate": tomorrow.isoformat(),
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert res.status_code == 400
    assert res.json()["errorCode"] == 1003


def test_add_workout_duplicate_date_and_slug_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts rejects duplicate date and slug with HTTP 409."""
    payload = {
        "title": "Initial Beatdown",
        "workoutDate": "2026-08-01",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
        "slug": "initial-beatdown",
    }
    res1 = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert res1.status_code == 201

    # Attempt second insertion with same date and slug
    res2 = client.post("/v2/workouts", json=payload, headers=auth_headers)
    assert res2.status_code == 409
    assert res2.json()["errorCode"] == 1007
    assert "already exists" in res2.json()["errorMessage"]


def test_add_workout_missing_required_entities_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST /v2/workouts rejects empty Qs, PAX, or AOs."""
    base_payload = {
        "title": "Test",
        "workoutDate": "2026-08-01",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }

    # Missing Qs
    p1 = base_payload.copy()
    p1["qic"] = []
    res1 = client.post("/v2/workouts", json=p1, headers=auth_headers)
    assert res1.status_code == 400
    assert res1.json()["errorCode"] == 1004

    # Missing PAX
    p2 = base_payload.copy()
    p2["pax"] = []
    res2 = client.post("/v2/workouts", json=p2, headers=auth_headers)
    assert res2.status_code == 400
    assert res2.json()["errorCode"] == 1005

    # Missing AOs
    p3 = base_payload.copy()
    p3["aos"] = []
    res3 = client.post("/v2/workouts", json=p3, headers=auth_headers)
    assert res3.status_code == 422 or res3.status_code == 400


def test_add_workout_unauthorized_without_token(client: TestClient) -> None:
    """Verify POST /v2/workouts returns 401 when token is missing."""
    res = client.post("/v2/workouts", json={"title": "No Token"})
    assert res.status_code == 401


def test_delete_workout_success_with_bearer_token(client: TestClient, db_session: Session, auth_headers: dict[str, str], admin_headers: dict[str, str]) -> None:
    """Verify DELETE /v2/workouts/{id} removes workout and all child records when authenticated."""
    # First create a workout
    create_res = client.post(
        "/v2/workouts",
        json={
            "title": "To Delete",
            "workoutDate": "2026-08-01",
            "qic": ["Dingo"],
            "pax": ["Dingo", "Lab Rat"],
            "aos": [{"name": "Gridiron"}],
            "body": "<p>Content</p>",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # Delete with admin bearer token
    delete_res = client.delete(
        f"/v2/workouts/{workout_id}",
        headers=admin_headers,
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["workoutId"] == workout_id

    # Verify deleted from DB
    assert db_session.query(Workout).filter(Workout.workout_id == workout_id).first() is None
    assert db_session.query(WorkoutDetails).filter(WorkoutDetails.workout_id == workout_id).first() is None
    assert db_session.query(WorkoutAO).filter(WorkoutAO.workout_id == workout_id).first() is None
    assert db_session.query(WorkoutQ).filter(WorkoutQ.workout_id == workout_id).first() is None
    assert db_session.query(WorkoutPax).filter(WorkoutPax.workout_id == workout_id).first() is None


def test_delete_workout_unauthorized_without_token(client: TestClient) -> None:
    """Verify DELETE /v2/workouts/{id} returns 401 without Bearer token."""
    res = client.delete("/v2/workouts/101")
    assert res.status_code == 401
    assert res.json()["errorCode"] == 4010


def test_delete_workout_not_found_404(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Verify DELETE /v2/workouts/99999 returns 404 for non-existent workout."""
    res = client.delete("/v2/workouts/99999", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["errorCode"] == 1001


def test_update_workout_success(client: TestClient, db_session: Session, auth_headers: dict[str, str]) -> None:
    """Verify PUT /v2/workouts/{id} successfully updates workout and replaces attendee records."""
    # 1. Create original workout by Dingo
    create_res = client.post(
        "/v2/workouts",
        json={
            "title": "Initial Beatdown",
            "workoutDate": "2026-08-01",
            "qic": "Dingo",
            "pax": "Dingo, Lab Rat",
            "aos": [{"name": "First Watch", "slug": "first-watch"}],
            "body": "<p>Initial Body</p>",
            "url": "https://f3rva.org/2026/08/01/initial-beatdown",
            "author": "Dingo",
            "slug": "initial-beatdown",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # 2. Update workout with revised details (as author Dingo)
    update_payload = {
        "title": "Updated Beatdown",
        "workoutDate": "2026-08-02",
        "qic": ["Splinter", "Swag"],
        "pax": ["Splinter", "Swag", "Bleeder"],
        "aos": [{"name": "Spider Run", "slug": "spider-run"}],
        "body": "<p>Updated Body with 100 Merkins</p>",
        "url": "https://f3rva.org/2026/08/02/updated-beatdown",
        "author": "Splinter",
        "slug": "updated-beatdown",
    }
    update_res = client.put(f"/v2/workouts/{workout_id}", json=update_payload, headers=auth_headers)
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["id"] == workout_id

    # 3. Verify DB record updates
    w = db_session.query(Workout).filter(Workout.workout_id == workout_id).first()
    assert w is not None
    assert w.title == "Updated Beatdown"
    assert w.workout_date == datetime.date(2026, 8, 2)
    assert w.author == "Splinter"
    assert w.slug == "updated-beatdown"
    assert w.backblast_url == "https://f3rva.org/2026/08/02/updated-beatdown"

    # Details updated
    det = db_session.query(WorkoutDetails).filter(WorkoutDetails.workout_id == workout_id).first()
    assert det is not None
    assert det.html_content == "<p>Updated Body with 100 Merkins</p>"

    # Qs replaced (now 2 Qs: Splinter, Swag)
    qs = db_session.query(WorkoutQ).filter(WorkoutQ.workout_id == workout_id).all()
    assert len(qs) == 2

    # PAX replaced (now 3 attendees)
    pax = db_session.query(WorkoutPax).filter(WorkoutPax.workout_id == workout_id).all()
    assert len(pax) == 3

    # AOs replaced (now Spider Run)
    aos = db_session.query(WorkoutAO).filter(WorkoutAO.workout_id == workout_id).all()
    assert len(aos) == 1


def test_update_workout_forbidden_for_non_author(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify PUT /v2/workouts/{id} rejects edits by a non-author, non-admin with 403."""
    # Create workout by Dingo
    create_res = client.post(
        "/v2/workouts",
        json={
            "title": "Dingo's Workout",
            "workoutDate": "2026-08-01",
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "First Watch"}],
            "author": "Dingo",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # Try to edit as Attila (not author, not admin)
    attila_token = create_access_token(data={"sub": "U999", "member_id": 999, "f3_name": "Attila", "role": "member"})
    attila_headers = {"Authorization": f"Bearer {attila_token}"}

    update_res = client.put(
        f"/v2/workouts/{workout_id}",
        json={
            "title": "Attila's Hijack",
            "workoutDate": "2026-08-01",
            "qic": ["Attila"],
            "pax": ["Attila"],
            "aos": [{"name": "First Watch"}],
        },
        headers=attila_headers,
    )
    assert update_res.status_code == 403
    assert update_res.json()["errorCode"] == 4003


def test_update_workout_not_found_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify PUT /v2/workouts/99999 returns 404 for non-existent workout."""
    payload = {
        "title": "Non-existent",
        "workoutDate": "2026-08-01",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.put("/v2/workouts/99999", json=payload, headers=auth_headers)
    assert res.status_code == 404
    assert res.json()["errorCode"] == 1001


def test_update_workout_validation_errors(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify PUT /v2/workouts/{id} rejects invalid date and future dates."""
    # Create workout first
    create_res = client.post(
        "/v2/workouts",
        json={
            "title": "Validation Test",
            "workoutDate": "2026-08-01",
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "Gridiron"}],
            "author": "Dingo",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # Invalid date format
    res_invalid_date = client.put(
        f"/v2/workouts/{workout_id}",
        json={
            "title": "Validation Test",
            "workoutDate": "invalid-date",
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "Gridiron"}],
        },
        headers=auth_headers,
    )
    assert res_invalid_date.status_code == 400
    assert res_invalid_date.json()["errorCode"] == 1002

    # Future date
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    res_future = client.put(
        f"/v2/workouts/{workout_id}",
        json={
            "title": "Validation Test",
            "workoutDate": tomorrow,
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "Gridiron"}],
        },
        headers=auth_headers,
    )
    assert res_future.status_code == 400
    assert res_future.json()["errorCode"] == 1003


def test_add_workout_auto_generates_url_from_settings_prefix(
    client: TestClient, db_session: Session, auth_headers: dict[str, str]
) -> None:
    """Verify POST /v2/workouts generates backblast_url using configurable BACKBLAST_URL_PREFIX."""
    with patch("src.services.workout_mutation_service.get_settings") as mock_settings:
        mock_settings.return_value.backblast_url_prefix = "https://custom.f3rva.org/"
        payload = {
            "title": "Custom Domain Test",
            "workoutDate": "2026-08-09",
            "qic": ["Dingo"],
            "pax": ["Dingo"],
            "aos": [{"name": "Gridiron"}],
            "slug": "custom-domain-test",
        }
        res = client.post("/v2/workouts", json=payload, headers=auth_headers)
        assert res.status_code == 201
        wid = res.json()["id"]

        w = db_session.query(Workout).filter(Workout.workout_id == wid).first()
        assert w is not None
        assert w.backblast_url == "https://custom.f3rva.org/2026/08/09/custom-domain-test"

