"""Unit and Integration Tests for Members & PAX Analytics Endpoints."""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.database import Base
from src.models.workout import AO, Member, MemberAlias, Workout, WorkoutAO, WorkoutPax, WorkoutQ


def seed_test_member_data(db: Session) -> dict[str, int]:
    """Helper fixture to insert mock members, aliases, workouts, and attendances."""
    Base.metadata.drop_all(bind=db.get_bind())
    Base.metadata.create_all(bind=db.get_bind())
    # 1. Insert Members (intentionally inserted in non-alphabetical order)
    m1 = Member(member_id=1, f3_name="Splinter")
    m2 = Member(member_id=2, f3_name="Dingo")
    m3 = Member(member_id=3, f3_name="Lab Rat")
    m4 = Member(member_id=4, f3_name="New Guy")  # Member with 0 workouts to test 0-division safety
    db.add_all([m1, m2, m3, m4])

    # 2. Insert Aliases
    alias1 = MemberAlias(member_id=2, f3_alias="Wild Dog")
    alias2 = MemberAlias(member_id=3, f3_alias="The Chemist")
    db.add_all([alias1, alias2])

    # 3. Insert AOs
    ao1 = AO(ao_id=1, description="Gridiron", slug="gridiron")
    ao2 = AO(ao_id=2, description="Dogpile", slug="dogpile")
    db.add_all([ao1, ao2])

    # 4. Insert Workouts
    w1 = Workout(
        workout_id=201,
        workout_date=datetime.date(2026, 8, 1),
        title="Gridiron Beatdown",
        author="Dingo",
        slug="gridiron-beatdown",
        backblast_url="https://f3rva.org/2026/08/01/gridiron-beatdown",
    )
    w2 = Workout(
        workout_id=202,
        workout_date=datetime.date(2026, 8, 3),
        title="Dogpile Endurance",
        author="Splinter",
        slug="dogpile-endurance",
        backblast_url="https://f3rva.org/2026/08/03/dogpile-endurance",
    )
    w3 = Workout(
        workout_id=203,
        workout_date=datetime.date(2026, 8, 5),
        title="Midweek Madness",
        author="Dingo",
        slug="midweek-madness",
        backblast_url="https://f3rva.org/2026/08/05/midweek-madness",
    )
    db.add_all([w1, w2, w3])
    db.flush()

    # 5. Map AOs
    db.add(WorkoutAO(workout_id=201, ao_id=1))
    db.add(WorkoutAO(workout_id=202, ao_id=2))
    db.add(WorkoutAO(workout_id=203, ao_id=1))

    # 6. Map Qs (Dingo led w1 and w3; Splinter led w2)
    db.add(WorkoutQ(workout_id=201, member_id=2))
    db.add(WorkoutQ(workout_id=202, member_id=1))
    db.add(WorkoutQ(workout_id=203, member_id=2))

    # 7. Map PAX (Dingo attended w1, w2, w3 -> 3 workouts, 2 Qs; Lab Rat attended w1, w2 -> 2 workouts, 0 Qs)
    db.add(WorkoutPax(workout_id=201, member_id=2))
    db.add(WorkoutPax(workout_id=201, member_id=3))
    db.add(WorkoutPax(workout_id=202, member_id=1))
    db.add(WorkoutPax(workout_id=202, member_id=2))
    db.add(WorkoutPax(workout_id=202, member_id=3))
    db.add(WorkoutPax(workout_id=203, member_id=2))

    db.commit()
    return {"splinter": 1, "dingo": 2, "lab_rat": 3, "new_guy": 4}


def test_get_all_members_alphabetical(client: TestClient, db_session: Session) -> None:
    """Verify that all members are returned ordered alphabetically by F3 name."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    names = [m["f3Name"] for m in data]
    assert names == ["Dingo", "Lab Rat", "New Guy", "Splinter"]


def test_get_member_by_id_full_profile(client: TestClient, db_session: Session) -> None:
    """Verify single member profile includes aliases, stats, and attended/Q'd workout history."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/2")
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == 2
    assert data["f3Name"] == "Dingo"

    # Aliases
    assert data["aliases"] == ["Wild Dog"]

    # Stats: Dingo has 3 attended workouts and 2 Qs -> Q ratio 2/3 = 0.6667
    assert data["stats"] is not None
    assert data["stats"]["numWorkouts"] == 3
    assert data["stats"]["numQs"] == 2
    assert round(data["stats"]["qRatio"], 2) == 0.67

    # Workouts attended (3 workouts)
    assert len(data["attendedWorkouts"]) == 3
    assert len(data["qdWorkouts"]) == 2


def test_get_member_stats_success(client: TestClient, db_session: Session) -> None:
    """Verify member statistical calculation endpoint."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/3/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == 3
    assert data["numWorkouts"] == 2
    assert data["numQs"] == 0
    assert data["qRatio"] == 0.0


def test_get_member_stats_zero_division_safety(client: TestClient, db_session: Session) -> None:
    """Verify that a member with 0 workouts returns 0.0 Q-ratio without mathematical division error."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/4/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == 4
    assert data["numWorkouts"] == 0
    assert data["numQs"] == 0
    assert data["qRatio"] == 0.0


def test_lookup_member_by_primary_name(client: TestClient, db_session: Session) -> None:
    """Verify case-insensitive search by primary F3 name."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/lookup?name=dingo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["memberId"] == 2
    assert data[0]["f3Name"] == "Dingo"


def test_lookup_member_by_alias(client: TestClient, db_session: Session) -> None:
    """Verify case-insensitive search by registered alias."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/lookup?name=chemist")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["memberId"] == 3
    assert data[0]["f3Name"] == "Lab Rat"


def test_lookup_member_empty_query_400(client: TestClient) -> None:
    """Verify 400 Bad Request when search query is empty whitespace."""
    response = client.get("/v2/members/lookup?name=%20%20")
    assert response.status_code == 400
    data = response.json()
    assert data["errorCode"] == 2002


def test_lookup_member_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 when no members match search criteria."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/lookup?name=NonExistentMember")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001


def test_get_member_by_id_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 when requesting non-existent member ID."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/9999")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001


def test_get_member_stats_not_found_404(client: TestClient, db_session: Session) -> None:
    """Verify 404 when requesting stats for non-existent member ID."""
    seed_test_member_data(db_session)

    response = client.get("/v2/members/9999/stats")
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001
