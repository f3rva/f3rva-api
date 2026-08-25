"""Unit and Integration Tests for Structured Workout Additions and Protected Deletions."""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.workout import AO, Workout, WorkoutAO, WorkoutDetails, WorkoutPax, WorkoutQ
from src.utils.security import create_access_token


def test_add_workout_with_aos_objects(client: TestClient, db_session: Session) -> None:
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
    response = client.post("/v2/workouts", json=payload)
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


def test_add_workout_with_list_inputs(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/workouts creates workout when Qs, PAX are lists and AO has auto-derived slug."""
    payload = {
        "title": "Dogpile Ruck",
        "workoutDate": "20260805",
        "qic": ["Splinter"],
        "pax": ["Splinter", "Lab Rat"],
        "aos": [{"name": "Dogpile"}],
    }
    response = client.post("/v2/workouts", json=payload)
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


def test_add_workout_date_formats(client: TestClient, db_session: Session) -> None:
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
        res = client.post("/v2/workouts", json=payload)
        assert res.status_code == 201
        w = db_session.query(Workout).filter(Workout.workout_id == res.json()["id"]).first()
        assert w is not None
        assert w.workout_date == expected


def test_add_workout_invalid_date_rejected(client: TestClient) -> None:
    """Verify POST /v2/workouts rejects invalid date format with 400."""
    payload = {
        "title": "Invalid Date Test",
        "workoutDate": "NotADate",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.post("/v2/workouts", json=payload)
    assert res.status_code == 400
    assert res.json()["errorCode"] == 1002


def test_add_workout_future_date_rejected(client: TestClient) -> None:
    """Verify POST /v2/workouts rejects future date with 400."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    payload = {
        "title": "Future Test",
        "workoutDate": tomorrow.isoformat(),
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.post("/v2/workouts", json=payload)
    assert res.status_code == 400
    assert res.json()["errorCode"] == 1003


def test_add_workout_missing_required_entities_rejected(client: TestClient) -> None:
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
    res1 = client.post("/v2/workouts", json=p1)
    assert res1.status_code == 400
    assert res1.json()["errorCode"] == 1004

    # Missing PAX
    p2 = base_payload.copy()
    p2["pax"] = []
    res2 = client.post("/v2/workouts", json=p2)
    assert res2.status_code == 400
    assert res2.json()["errorCode"] == 1005

    # Missing AOs
    p3 = base_payload.copy()
    p3["aos"] = []
    res3 = client.post("/v2/workouts", json=p3)
    assert res3.status_code == 422 or res3.status_code == 400


def test_delete_workout_success_with_bearer_token(client: TestClient, db_session: Session) -> None:
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
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # Delete with admin bearer token
    token = create_access_token(data={"sub": "admin"})
    delete_res = client.delete(
        f"/v2/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {token}"},
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


def test_delete_workout_not_found_404(client: TestClient) -> None:
    """Verify DELETE /v2/workouts/99999 returns 404 for non-existent workout."""
    token = create_access_token(data={"sub": "admin"})
    res = client.delete("/v2/workouts/99999", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    assert res.json()["errorCode"] == 1001


def test_update_workout_success(client: TestClient, db_session: Session) -> None:
    """Verify PUT /v2/workouts/{id} successfully updates workout and replaces attendee records."""
    # 1. Create original workout
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
    )
    assert create_res.status_code == 201
    workout_id = create_res.json()["id"]

    # 2. Update workout with revised details
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
    update_res = client.put(f"/v2/workouts/{workout_id}", json=update_payload)
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


def test_update_workout_not_found_404(client: TestClient) -> None:
    """Verify PUT /v2/workouts/99999 returns 404 for non-existent workout."""
    payload = {
        "title": "Non-existent",
        "workoutDate": "2026-08-01",
        "qic": ["Dingo"],
        "pax": ["Dingo"],
        "aos": [{"name": "Gridiron"}],
    }
    res = client.put("/v2/workouts/99999", json=payload)
    assert res.status_code == 404
    assert res.json()["errorCode"] == 1001


def test_update_workout_validation_errors(client: TestClient) -> None:
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
        },
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
    )
    assert res_future.status_code == 400
    assert res_future.json()["errorCode"] == 1003

