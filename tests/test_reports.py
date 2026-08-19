"""Unit and Integration Tests for Analytical Reports, Leaderboards & Metrics."""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.database import Base
from src.models.workout import AO, Member, Workout, WorkoutAO, WorkoutPax, WorkoutQ


def seed_test_report_data(db: Session) -> dict[str, int]:
    """Helper fixture to insert mock members, AOs, and multi-date workout history."""
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

    # 3. Insert Workouts across multiple dates (Sundays, Mondays, Wednesdays)
    # 2026-08-02 is Sunday, 2026-08-03 is Monday, 2026-08-05 is Wednesday, 2026-08-10 is Monday
    w1 = Workout(
        workout_id=301,
        workout_date=datetime.date(2026, 8, 2),  # Sunday
        title="Gridiron Sunday Beatdown",
        author="Dingo",
        slug="gridiron-sunday-beatdown",
        backblast_url="https://f3rva.org/2026/08/02/gridiron-sunday-beatdown",
    )
    w2 = Workout(
        workout_id=302,
        workout_date=datetime.date(2026, 8, 3),  # Monday
        title="Dogpile Monday Run",
        author="Splinter",
        slug="dogpile-monday-run",
        backblast_url="https://f3rva.org/2026/08/03/dogpile-monday-run",
    )
    w3 = Workout(
        workout_id=303,
        workout_date=datetime.date(2026, 8, 5),  # Wednesday
        title="Gridiron Midweek",
        author="Dingo",
        slug="gridiron-midweek",
        backblast_url="https://f3rva.org/2026/08/05/gridiron-midweek",
    )
    w4 = Workout(
        workout_id=304,
        workout_date=datetime.date(2026, 8, 10),  # Monday
        title="Gridiron Monday Special",
        author="Lab Rat",
        slug="gridiron-monday-special",
        backblast_url="https://f3rva.org/2026/08/10/gridiron-monday-special",
    )
    db.add_all([w1, w2, w3, w4])
    db.flush()

    # 4. Map AOs (w1, w3, w4 at Gridiron; w2 at Dogpile)
    db.add(WorkoutAO(workout_id=301, ao_id=1))
    db.add(WorkoutAO(workout_id=302, ao_id=2))
    db.add(WorkoutAO(workout_id=303, ao_id=1))
    db.add(WorkoutAO(workout_id=304, ao_id=1))

    # 5. Map Qs (Dingo led w1 and w3; Splinter led w2; Lab Rat led w4)
    db.add(WorkoutQ(workout_id=301, member_id=1))
    db.add(WorkoutQ(workout_id=302, member_id=3))
    db.add(WorkoutQ(workout_id=303, member_id=1))
    db.add(WorkoutQ(workout_id=304, member_id=2))

    # 6. Map PAX Attendees
    # Dingo attended w1, w3, w4 at Gridiron (3 consecutive Gridiron workouts!) + w2 at Dogpile (Total 4 workouts, 2 Qs)
    db.add(WorkoutPax(workout_id=301, member_id=1))
    db.add(WorkoutPax(workout_id=302, member_id=1))
    db.add(WorkoutPax(workout_id=303, member_id=1))
    db.add(WorkoutPax(workout_id=304, member_id=1))

    # Lab Rat attended w1, w2, w4 (Total 3 workouts, 1 Q)
    db.add(WorkoutPax(workout_id=301, member_id=2))
    db.add(WorkoutPax(workout_id=302, member_id=2))
    db.add(WorkoutPax(workout_id=304, member_id=2))

    # Splinter attended w2 (Total 1 workout, 1 Q)
    db.add(WorkoutPax(workout_id=302, member_id=3))

    db.commit()
    return {"gridiron": 1, "dogpile": 2}


def test_get_attendance_leaderboard_default_sorting(client: TestClient, db_session: Session) -> None:
    """Verify attendance leaderboard ranked by workout count descending."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/attendance")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    # Dingo (4 workouts) -> Lab Rat (3 workouts) -> Splinter (1 workout)
    assert data[0]["f3Name"] == "Dingo"
    assert data[0]["numWorkouts"] == 4
    assert data[0]["numQs"] == 2
    assert data[0]["qRatio"] == 0.5

    assert data[1]["f3Name"] == "Lab Rat"
    assert data[1]["numWorkouts"] == 3
    assert data[1]["numQs"] == 1

    assert data[2]["f3Name"] == "Splinter"
    assert data[2]["numWorkouts"] == 1
    assert data[2]["numQs"] == 1
    assert data[2]["qRatio"] == 1.0


def test_get_attendance_leaderboard_sorted_by_q(client: TestClient, db_session: Session) -> None:
    """Verify attendance leaderboard ranked by Q count descending."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/attendance?sortBy=q")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["f3Name"] == "Dingo"
    assert data[0]["numQs"] == 2


def test_get_attendance_leaderboard_sorted_by_ratio(client: TestClient, db_session: Session) -> None:
    """Verify attendance leaderboard ranked by Q ratio descending."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/attendance?sortBy=ratio")
    assert response.status_code == 200
    data = response.json()
    # Splinter has 1 workout and 1 Q -> ratio 1.0
    assert data[0]["f3Name"] == "Splinter"
    assert data[0]["qRatio"] == 1.0


def test_get_attendance_leaderboard_min_thresholds_and_exclusion(client: TestClient, db_session: Session) -> None:
    """Verify minQs and minWorkouts filters and exclusion of member 123."""
    seed_test_report_data(db_session)
    # Add member 123 (All PAX) to verify exclusion
    m_all = Member(member_id=123, f3_name="All PAX")
    db_session.add(m_all)
    db_session.add(WorkoutPax(workout_id=301, member_id=123))
    db_session.commit()

    # Query with minQs=2: only Dingo (2 Qs) qualifies
    response = client.get("/v2/reports/attendance?minQs=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["f3Name"] == "Dingo"

    # Query with minWorkouts=3: Dingo (4) and Lab Rat (3) qualify, All PAX (123) is excluded
    response2 = client.get("/v2/reports/attendance?minWorkouts=3")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2) == 2
    assert all(m["memberId"] != 123 for m in data2)


def test_get_attendance_leaderboard_date_range_filter(client: TestClient, db_session: Session) -> None:
    """Verify attendance leaderboard with date range filters."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/attendance?startDate=2026-08-04&endDate=2026-08-11")
    assert response.status_code == 200
    data = response.json()
    # In range 8/4 - 8/11: workouts 303 (8/5) and 304 (8/10). Dingo attended both (2), Lab Rat attended 304 (1)
    assert len(data) == 2
    assert data[0]["f3Name"] == "Dingo"
    assert data[0]["numWorkouts"] == 2


def test_get_ao_attendance_summary(client: TestClient, db_session: Session) -> None:
    """Verify AO-level workout counts, total attendees, and average PAX."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/ao")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Gridiron has 3 workouts (301: 2 pax, 303: 1 pax, 304: 2 pax -> total 5 pax, avg 5/3 = 1.67)
    # Dogpile has 1 workout (302: 3 pax -> total 3 pax, avg 3/1 = 3.0)
    # Ordered by averagePax desc: Dogpile (3.0) -> Gridiron (1.67)
    assert data[0]["description"] == "Dogpile"
    assert data[0]["totalWorkouts"] == 1
    assert data[0]["totalPax"] == 3
    assert data[0]["averagePax"] == 3.0

    assert data[1]["description"] == "Gridiron"
    assert data[1]["totalWorkouts"] == 3
    assert data[1]["totalPax"] == 5
    assert data[1]["averagePax"] == 1.67


def test_get_ao_leaderboard_with_streakers(client: TestClient, db_session: Session) -> None:
    """Verify AO leaderboard calculates top Qs, top PAX, and consecutive attendance streaks."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/ao/1/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert data["aoId"] == 1
    assert data["description"] == "Gridiron"

    # Top Qs at Gridiron: Dingo (2 Qs), Lab Rat (1 Q)
    assert len(data["topQs"]) == 2
    assert data["topQs"][0]["name"] == "Dingo"
    assert data["topQs"][0]["count"] == 2

    # Top PAX at Gridiron: Dingo (3 workouts), Lab Rat (2 workouts)
    assert len(data["topPax"]) == 2
    assert data["topPax"][0]["name"] == "Dingo"
    assert data["topPax"][0]["count"] == 3

    # Streakers at Gridiron:
    # Most recent workout is 304 (8/10). Attendees: Dingo, Lab Rat.
    # Dingo attended 304, 303, 301 -> Streak of 3!
    # Lab Rat attended 304, but missed 303 -> Streak of 1!
    assert len(data["streakers"]) == 2
    assert data["streakers"][0]["name"] == "Dingo"
    assert data["streakers"][0]["count"] == 3
    assert data["streakers"][1]["name"] == "Lab Rat"
    assert data["streakers"][1]["count"] == 1


def test_get_ao_leaderboard_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 response when querying leaderboard for non-existent AO."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/ao/9999/leaderboard")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 3001


def test_get_day_of_week_attendance(client: TestClient, db_session: Session) -> None:
    """Verify breakdown across all 7 days of the week."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/day-of-week")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 7

    # Day 1: Sunday (1 workout, 2 pax)
    sunday = next(d for d in data if d["dayId"] == 1)
    assert sunday["dayName"] == "Sunday"
    assert sunday["workoutCount"] == 1
    assert sunday["totalPax"] == 2

    # Day 2: Monday (2 workouts: 302 and 304 -> total 3 + 2 = 5 pax)
    monday = next(d for d in data if d["dayId"] == 2)
    assert monday["dayName"] == "Monday"
    assert monday["workoutCount"] == 2
    assert monday["totalPax"] == 5


def test_get_member_distribution_success(client: TestClient, db_session: Session) -> None:
    """Verify member distribution across multiple AOs."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/members/1/distribution")
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == 1
    assert data["f3Name"] == "Dingo"

    # Dingo attended Gridiron (3 workouts, 2 Qs) and Dogpile (1 workout, 0 Qs)
    assert len(data["distribution"]) == 2
    gridiron = next(d for d in data["distribution"] if d["description"] == "Gridiron")
    assert gridiron["paxCount"] == 3
    assert gridiron["qCount"] == 2

    dogpile = next(d for d in data["distribution"] if d["description"] == "Dogpile")
    assert dogpile["paxCount"] == 1
    assert dogpile["qCount"] == 0


def test_get_member_distribution_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 for member distribution lookup on non-existent member."""
    seed_test_report_data(db_session)

    response = client.get("/v2/reports/members/9999/distribution")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001
