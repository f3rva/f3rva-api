"""Unit and Integration Tests for Admin Operations, JWT Auth, and Alias Merging."""

from __future__ import annotations

import datetime
from fastapi.testclient import TestClient
import jwt
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.workout import AO, Member, MemberAlias, MemberAliasAudit, Workout, WorkoutAO, WorkoutPax, WorkoutQ
from src.utils.security import create_access_token


def seed_admin_test_data(db: Session) -> dict[str, int]:
    """Helper fixture to insert mock members, workouts, and attendances for alias merging."""
    # 1. Members (Primary: Dingo (id=1), Duplicate to merge: Wild Dingo (id=2), Third: Lab Rat (id=3))
    m1 = Member(member_id=1, f3_name="Dingo")
    m2 = Member(member_id=2, f3_name="Wild Dingo")
    m3 = Member(member_id=3, f3_name="Lab Rat")
    db.add_all([m1, m2, m3])

    # 2. AO
    ao1 = AO(ao_id=1, description="Gridiron", slug="gridiron")
    db.add(ao1)

    # 3. Workouts (w1 attended by both 1 & 2; w2 attended only by 2; w3 Q'd by 2)
    w1 = Workout(workout_id=401, workout_date=datetime.date(2026, 8, 1), title="W1", author="Dingo", slug="w1")
    w2 = Workout(workout_id=402, workout_date=datetime.date(2026, 8, 2), title="W2", author="Wild Dingo", slug="w2")
    w3 = Workout(workout_id=403, workout_date=datetime.date(2026, 8, 3), title="W3", author="Wild Dingo", slug="w3")
    db.add_all([w1, w2, w3])
    db.flush()

    db.add(WorkoutAO(workout_id=401, ao_id=1))
    db.add(WorkoutAO(workout_id=402, ao_id=1))
    db.add(WorkoutAO(workout_id=403, ao_id=1))

    # Q: w3 Q'd by Wild Dingo (id=2)
    db.add(WorkoutQ(workout_id=403, member_id=2))

    # PAX: w1 has both Dingo and Wild Dingo; w2 has Wild Dingo and Lab Rat
    db.add(WorkoutPax(workout_id=401, member_id=1))
    db.add(WorkoutPax(workout_id=401, member_id=2))
    db.add(WorkoutPax(workout_id=402, member_id=2))
    db.add(WorkoutPax(workout_id=402, member_id=3))

    db.commit()
    return {"dingo": 1, "wild_dingo": 2, "lab_rat": 3}


def test_admin_login_success(client: TestClient) -> None:
    """Verify POST /v2/admin/login with correct credentials returns valid JWT token."""
    response = client.post("/v2/admin/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert data["expiresIn"] == 86400


def test_admin_login_invalid_credentials(client: TestClient) -> None:
    """Verify POST /v2/admin/login returns 401 on incorrect password."""
    response = client.post("/v2/admin/login", json={"username": "admin", "password": "wrong-password"})
    assert response.status_code == 401
    data = response.json()
    assert data["errorCode"] == 4001


def test_submit_alias_claim_request_success(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request creates pending alias request."""
    seed_admin_test_data(db_session)

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["primaryMember"]["memberId"] == 1
    assert data["aliasMember"]["memberId"] == 2


def test_submit_alias_claim_request_same_member_rejected(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request rejects same member ID for primary and alias."""
    seed_admin_test_data(db_session)

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 1},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["errorCode"] == 2003


def test_submit_alias_claim_request_unknown_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request returns 404 if member does not exist."""
    seed_admin_test_data(db_session)

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 9999},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001


def test_submit_alias_claim_request_duplicate_conflict(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request returns 409 if pending request already exists."""
    seed_admin_test_data(db_session)

    # First request
    r1 = client.post("/v2/aliases/request", json={"primaryMemberId": 1, "aliasMemberId": 2})
    assert r1.status_code == 201

    # Duplicate request
    r2 = client.post("/v2/aliases/request", json={"primaryMemberId": 1, "aliasMemberId": 2})
    assert r2.status_code == 409
    assert r2.json()["errorCode"] == 2004


def test_get_pending_alias_requests_unauthorized_without_token(client: TestClient) -> None:
    """Verify GET /v2/admin/aliases/requests rejects requests without authorization token."""
    response = client.get("/v2/admin/aliases/requests")
    assert response.status_code == 401
    assert response.json()["errorCode"] == 4010


def test_get_pending_alias_requests_with_jwt(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/admin/aliases/requests returns pending requests for authenticated admin."""
    seed_admin_test_data(db_session)
    client.post("/v2/aliases/request", json={"primaryMemberId": 1, "aliasMemberId": 2})

    token = create_access_token(data={"sub": "admin"})
    response = client.get("/v2/admin/aliases/requests", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["primaryMember"]["f3Name"] == "Dingo"
    assert data[0]["aliasMember"]["f3Name"] == "Wild Dingo"


def test_approve_alias_request_merges_records(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/aliases/approve/{primary_id}/{alias_id} reassigns workouts, creates audit, and merges member."""
    seed_admin_test_data(db_session)
    client.post("/v2/aliases/request", json={"primaryMemberId": 1, "aliasMemberId": 2})

    token = create_access_token(data={"sub": "admin"})
    approve_res = client.post(
        "/v2/admin/aliases/approve/1/2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # Verify duplicate member 2 is deleted
    m2 = db_session.query(Member).filter(Member.member_id == 2).first()
    assert m2 is None

    # Verify alias mapping exists for Dingo -> 'Wild Dingo'
    alias_entry = db_session.query(MemberAlias).filter(MemberAlias.member_id == 1).first()
    assert alias_entry is not None
    assert alias_entry.f3_alias == "Wild Dingo"

    # Verify audit entries were recorded
    audit_entries = db_session.query(MemberAliasAudit).all()
    assert len(audit_entries) > 0

    # Verify workout attendance was merged
    # w2 (402) attendance reassigned to Dingo (id=1)
    w2_pax = db_session.query(WorkoutPax).filter(WorkoutPax.workout_id == 402, WorkoutPax.member_id == 1).first()
    assert w2_pax is not None

    # w3 (403) Q reassigned to Dingo (id=1)
    w3_q = db_session.query(WorkoutQ).filter(WorkoutQ.workout_id == 403, WorkoutQ.member_id == 1).first()
    assert w3_q is not None


def test_reject_alias_request(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/aliases/reject/{primary_id}/{alias_id} marks status as rejected."""
    seed_admin_test_data(db_session)
    client.post("/v2/aliases/request", json={"primaryMemberId": 1, "aliasMemberId": 2})

    token = create_access_token(data={"sub": "admin"})
    reject_res = client.post(
        "/v2/admin/aliases/reject/1/2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"


def test_jwt_expired_token_rejected(client: TestClient) -> None:
    """Verify expired JWT token returns 401."""
    settings = get_settings()
    expired_token = jwt.encode(
        {"sub": "admin", "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    response = client.get("/v2/admin/aliases/requests", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["errorCode"] == 4011


def test_jwt_invalid_token_rejected(client: TestClient) -> None:
    """Verify malformed or invalid token signature returns 401."""
    response = client.get("/v2/admin/aliases/requests", headers={"Authorization": "Bearer invalid.malformed.token"})
    assert response.status_code == 401
    assert response.json()["errorCode"] == 4010
