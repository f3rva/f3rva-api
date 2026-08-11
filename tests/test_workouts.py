"""Unit and Integration Tests for Workouts & Backblasts Endpoints."""

from __future__ import annotations

import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.database import Base
from src.models.workout import AO, Member, Workout, WorkoutAO, WorkoutPax, WorkoutQ


def seed_test_workout_data(db: Session) -> dict[str, int]:
    """Helper fixture to insert mock workout records into in-memory SQLite database."""
    Base.metadata.drop_all(bind=db.get_bind())
    Base.metadata.create_all(bind=db.get_bind())
    # 1. Insert Members
    m1 = Member(member_id=1, f3_name="Dingo")
    m2 = Member(member_id=2, f3_name="Lab Rat")
    m3 = Member(member_id=3, f3_name="Splinter")
    db.add_all([m1, m2, m3])

    # 2. Insert AOs
    ao1 = AO(ao_id=1, description="Gridiron", slug="gridiron")
    ao2 = AO(ao_id=2, description="Dogpile", slug="dogpile")
    db.add_all([ao1, ao2])

    # 3. Insert Workouts (Workout 101 is tagged with MULTIPLE AOs: Gridiron + Dogpile)
    w1 = Workout(
        workout_id=101,
        workout_date=datetime.date(2026, 8, 7),
        title="Beatdown at Gridiron",
        author="Dingo",
        slug="beatdown-at-gridiron",
        backblast_url="https://f3rva.org/2026/08/07/beatdown-at-gridiron",
    )
    w2 = Workout(
        workout_id=102,
        workout_date=datetime.date(2026, 7, 15),
        title="Summer Sizzle at Dogpile",
        author="Lab Rat",
        slug="summer-sizzle-at-dogpile",
        backblast_url="https://f3rva.org/2026/07/15/summer-sizzle-at-dogpile",
    )
    db.add_all([w1, w2])
    db.flush()

    # 4. Map AOs (Workout 101 tagged with BOTH AO 1 and AO 2)
    db.add(WorkoutAO(workout_id=101, ao_id=1))
    db.add(WorkoutAO(workout_id=101, ao_id=2))
    db.add(WorkoutAO(workout_id=102, ao_id=2))

    # 5. Map Qs (Workout 101 co-led by BOTH Member 1 and Member 2)
    db.add(WorkoutQ(workout_id=101, member_id=1))
    db.add(WorkoutQ(workout_id=101, member_id=2))
    db.add(WorkoutQ(workout_id=102, member_id=2))

    # 6. Map PAX Attendees
    db.add(WorkoutPax(workout_id=101, member_id=1))
    db.add(WorkoutPax(workout_id=101, member_id=2))
    db.add(WorkoutPax(workout_id=101, member_id=3))
    db.add(WorkoutPax(workout_id=102, member_id=2))
    db.add(WorkoutPax(workout_id=102, member_id=3))

    db.commit()
    return {"workout1": 101, "workout2": 102}


def test_get_recent_workouts(client: TestClient, db_session: Session) -> None:
    """Verify paginated recent workouts are returned ordered by date descending with all multi-AOs and Qs preserved."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts?page=1&results=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["workoutId"] == 101
    assert data[0]["title"] == "Beatdown at Gridiron"
    assert data[0]["paxCount"] == 3

    # Assert multiple AOs are completely preserved with zero data loss
    assert len(data[0]["ao"]) == 2
    ao_names = [a["description"] for a in data[0]["ao"]]
    assert "Gridiron" in ao_names
    assert "Dogpile" in ao_names

    # Assert multiple Qs are completely preserved
    assert len(data[0]["q"]) == 2
    q_names = [q["f3Name"] for q in data[0]["q"]]
    assert "Dingo" in q_names
    assert "Lab Rat" in q_names


def test_get_workouts_pagination_empty(client: TestClient, db_session: Session) -> None:
    """Verify 404 is returned when page offset exceeds available data."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts?page=10&results=20")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 1001
    assert "Workout not found" in data["errorMessage"]


def test_get_workouts_by_year(client: TestClient, db_session: Session) -> None:
    """Verify year-only filtering returns workouts within that calendar year."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts/by-date?year=2026")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_workouts_by_month(client: TestClient, db_session: Session) -> None:
    """Verify month filtering returns workouts only within that specific month."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts/by-date?year=2026&month=8")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["workoutId"] == 101


def test_get_workouts_by_exact_day(client: TestClient, db_session: Session) -> None:
    """Verify exact year-month-day filter returns matching workout."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts/by-date?year=2026&month=7&day=15")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["workoutId"] == 102
    assert data[0]["workoutDate"] == "2026-07-15"


def test_get_workouts_day_without_month_returns_400(client: TestClient) -> None:
    """Verify 400 Bad Request if day parameter is provided without a month."""
    response = client.get("/v2/workouts/by-date?year=2026&day=15")
    assert response.status_code == 400
    data = response.json()
    assert data["errorCode"] == 1002


def test_get_workout_by_id_with_pax_roster(client: TestClient, db_session: Session) -> None:
    """Verify single workout lookup includes the full PAX attendee roster and multiple AOs."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts/101")
    assert response.status_code == 200
    data = response.json()
    assert data["workoutId"] == 101
    assert data["paxCount"] == 3
    assert len(data["ao"]) == 2
    assert len(data["q"]) == 2
    assert data["pax"] is not None
    assert len(data["pax"]) == 3
    pax_names = [p["f3Name"] for p in data["pax"]]
    assert "Dingo" in pax_names
    assert "Lab Rat" in pax_names
    assert "Splinter" in pax_names


def test_get_workout_by_date_and_slug(client: TestClient, db_session: Session) -> None:
    """Verify lookup by date components and URL slug."""
    seed_test_workout_data(db_session)

    response = client.get(
        "/v2/workouts/by-date-slug?year=2026&month=8&day=7&slug=beatdown-at-gridiron"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workoutId"] == 101
    assert data["title"] == "Beatdown at Gridiron"


def test_get_workouts_by_ao_id_and_slug(client: TestClient, db_session: Session) -> None:
    """Verify filtering workouts by numeric AO ID and AO slug."""
    seed_test_workout_data(db_session)

    # Test by AO ID
    response_id = client.get("/v2/workouts/ao/1")
    assert response_id.status_code == 200
    assert len(response_id.json()) == 1
    assert response_id.json()[0]["workoutId"] == 101

    # Test by AO Slug
    response_slug = client.get("/v2/workouts/ao/dogpile")
    assert response_slug.status_code == 200
    # Both workout 101 (Gridiron+Dogpile) and 102 (Dogpile) are matched
    assert len(response_slug.json()) == 2


def test_workout_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 response for non-existent workout ID."""
    seed_test_workout_data(db_session)

    response = client.get("/v2/workouts/9999")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 1001
    assert "Workout not found" in data["errorMessage"]
