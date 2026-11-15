"""Unit and Integration Tests for Admin Operations, JWT Auth, and Alias Merging."""

from __future__ import annotations

import datetime

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.database import Base
from src.config.settings import get_settings
from src.models.workout import (
    AO,
    Member,
    MemberAlias,
    MemberAliasAudit,
    MemberRole,
    MemberSlack,
    Workout,
    WorkoutAO,
    WorkoutPax,
    WorkoutQ,
)
from src.utils.security import create_access_token


def seed_admin_test_data(db: Session) -> dict[str, int]:
    """Helper fixture to insert mock members, workouts, and attendances for alias merging."""
    Base.metadata.drop_all(bind=db.get_bind())
    Base.metadata.create_all(bind=db.get_bind())
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

    # Seed Member 1 as initial admin in MEMBER_ROLE
    db.add(MemberRole(member_id=1, role="admin", granted_by=1))

    db.commit()
    return {"dingo": 1, "wild_dingo": 2, "lab_rat": 3}


def test_admin_get_roles_and_grant_revoke_lifecycle(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/admin/roles, POST /v2/admin/members/{id}/roles, and DELETE /v2/admin/members/{id}/roles/{role}."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(
        data={"sub": "U1", "member_id": 1, "f3_name": "Dingo", "role": "admin", "roles": ["admin", "member"]}
    )

    # 1. List existing roles (Member 1 seeded as admin)
    list_res = client.get("/v2/admin/roles", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_res.status_code == 200
    roles_data = list_res.json()
    assert len(roles_data) == 1
    assert roles_data[0]["memberId"] == 1
    assert roles_data[0]["f3Name"] == "Dingo"
    assert roles_data[0]["role"] == "admin"

    # 2. Grant admin role to Member 3 (Lab Rat)
    grant_res = client.post(
        "/v2/admin/members/3/roles",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert grant_res.status_code == 201
    granted = grant_res.json()
    assert granted["memberId"] == 3
    assert granted["f3Name"] == "Lab Rat"
    assert granted["role"] == "admin"
    assert granted["grantedByMemberId"] == 1
    assert granted["grantedByF3Name"] == "Dingo"

    # 3. Granting again is idempotent
    grant_again_res = client.post(
        "/v2/admin/members/3/roles",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert grant_again_res.status_code == 201
    assert grant_again_res.json()["memberId"] == 3

    # 4. Revoke admin role from Member 3
    revoke_res = client.delete(
        "/v2/admin/members/3/roles/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["memberId"] == 3
    assert revoke_res.json()["role"] == "admin"


def test_admin_role_validation_and_self_revoke_guard(client: TestClient, db_session: Session) -> None:
    """Verify invalid role returns 400, unknown member returns 404, and self-revocation is blocked with 400."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(
        data={"sub": "U1", "member_id": 1, "f3_name": "Dingo", "role": "admin", "roles": ["admin", "member"]}
    )

    # Invalid role name -> 400
    bad_role_res = client.post(
        "/v2/admin/members/3/roles",
        json={"role": "super_overlord"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert bad_role_res.status_code == 400
    assert bad_role_res.json()["errorCode"] == 4004

    # Unknown member -> 404
    missing_member_res = client.post(
        "/v2/admin/members/9999/roles",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert missing_member_res.status_code == 404
    assert missing_member_res.json()["errorCode"] == 2001

    # Self-revocation guard -> 400
    self_revoke_res = client.delete(
        "/v2/admin/members/1/roles/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert self_revoke_res.status_code == 400
    assert self_revoke_res.json()["errorCode"] == 4005

    # Revoking non-existent role assignment -> 404
    missing_role_res = client.delete(
        "/v2/admin/members/3/roles/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert missing_role_res.status_code == 404
    assert missing_role_res.json()["errorCode"] == 4006


def test_merge_members_reconciles_member_roles(client: TestClient, db_session: Session) -> None:
    """Verify merging members transfers MEMBER_ROLE entries and resolves conflicts cleanly."""
    seed_admin_test_data(db_session)
    # Give Member 2 (Wild Dingo) admin role and merge into Member 3 (Lab Rat, who has no roles yet)
    db_session.add(MemberRole(member_id=2, role="admin", granted_by=1))
    db_session.commit()

    admin_token = create_access_token(
        data={"sub": "U1", "member_id": 1, "f3_name": "Dingo", "role": "admin", "roles": ["admin", "member"]}
    )
    merge_res = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 3, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert merge_res.status_code == 200

    # Verify Member 3 inherited the 'admin' role from Member 2
    inherited_role = db_session.query(MemberRole).filter_by(member_id=3, role="admin").first()
    assert inherited_role is not None


def test_submit_alias_claim_request_success(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request creates pending alias request for authenticated member."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["primaryMember"]["memberId"] == 1
    assert data["aliasMember"]["memberId"] == 2


def test_submit_alias_claim_request_unauthorized_without_token(client: TestClient) -> None:
    """Verify POST /v2/aliases/request rejects unauthenticated requests with 401."""
    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
    )
    assert response.status_code == 401
    assert response.json()["errorCode"] == 4010


def test_submit_alias_claim_request_forbidden_for_other_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request rejects non-admin claiming alias for a different member ID."""
    seed_admin_test_data(db_session)
    other_member_token = create_access_token(data={"sub": "slack:U2", "member_id": 2, "role": "member"})

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 3},
        headers={"Authorization": f"Bearer {other_member_token}"},
    )
    assert response.status_code == 403
    assert response.json()["errorCode"] == 4003


def test_submit_alias_claim_request_admin_allowed_for_any_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request allows admin to submit request for any member."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(data={"sub": "admin", "role": "admin"})

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["primaryMember"]["memberId"] == 1


def test_submit_alias_claim_request_same_member_rejected(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request rejects same member ID for primary and alias."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 1},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["errorCode"] == 2003


def test_submit_alias_claim_request_unknown_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request returns 404 if member does not exist."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 9999},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["errorCode"] == 2001


def test_submit_alias_claim_request_duplicate_conflict(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/aliases/request returns 409 if pending request already exists."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    # First request
    r1 = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r1.status_code == 201

    # Duplicate request
    r2 = client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["errorCode"] == 2004


def test_get_public_pending_alias_requests(client: TestClient, db_session: Session) -> None:
    """Verify public GET /v2/aliases/requests returns pending requests without token."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})
    client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    response = client.get("/v2/aliases/requests")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["primaryMember"]["f3Name"] == "Dingo"


def test_get_pending_alias_requests_unauthorized_without_token(client: TestClient) -> None:
    """Verify GET /v2/admin/aliases/requests rejects requests without authorization token."""
    response = client.get("/v2/admin/aliases/requests")
    assert response.status_code == 401
    assert response.json()["errorCode"] == 4010


def test_get_pending_alias_requests_with_jwt(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/admin/aliases/requests returns pending requests for authenticated admin."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(data={"sub": "admin", "role": "admin"})
    client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get("/v2/admin/aliases/requests", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["primaryMember"]["f3Name"] == "Dingo"
    assert data[0]["aliasMember"]["f3Name"] == "Wild Dingo"


def test_approve_alias_request_merges_records(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/aliases/approve/{primary_id}/{alias_id} reassigns workouts, creates audit, and merges member."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(data={"sub": "admin", "role": "admin"})
    client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    token = create_access_token(data={"sub": "admin", "role": "admin"})
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
    w2_pax = db_session.query(WorkoutPax).filter(WorkoutPax.workout_id == 402, WorkoutPax.member_id == 1).first()
    assert w2_pax is not None

    w3_q = db_session.query(WorkoutQ).filter(WorkoutQ.workout_id == 403, WorkoutQ.member_id == 1).first()
    assert w3_q is not None


def test_reject_alias_request(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/aliases/reject/{primary_id}/{alias_id} marks status as rejected."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(data={"sub": "admin", "role": "admin"})
    client.post(
        "/v2/aliases/request",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    reject_res = client.post(
        "/v2/admin/aliases/reject/1/2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"


def test_direct_merge_members(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/members/merge merges members directly without requiring prior request."""
    seed_admin_test_data(db_session)

    token = create_access_token(data={"sub": "admin", "role": "admin"})
    merge_res = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert merge_res.status_code == 200
    assert merge_res.json()["status"] == "approved"

    # Verify duplicate member 2 deleted
    assert db_session.query(Member).filter(Member.member_id == 2).first() is None


def test_jwt_expired_token_rejected(client: TestClient) -> None:
    """Verify expired JWT token returns 401."""
    settings = get_settings()
    expired_token = jwt.encode(
        {"sub": "admin", "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)},
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


def test_merge_members_resolves_member_slack_conflicts(client: TestClient, db_session: Session) -> None:
    """Verify when both primary and alias have MEMBER_SLACK records for same team, primary is kept and alias deleted."""
    seed_admin_test_data(db_session)

    # Primary member 1 has Slack record in T_PROD
    db_session.add(MemberSlack(member_id=1, slack_team_id="T_PROD", slack_user_id="U_PRIMARY", slack_display_name="Dingo"))
    # Alias member 2 also has Slack record in T_PROD
    db_session.add(MemberSlack(member_id=2, slack_team_id="T_PROD", slack_user_id="U_ALIAS", slack_display_name="Wild Dingo"))
    db_session.commit()

    token = create_access_token(data={"sub": "admin", "role": "admin"})
    merge_res = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert merge_res.status_code == 200

    # Verify primary Slack mapping is retained and alias Slack mapping deleted
    assert db_session.query(MemberSlack).filter_by(slack_team_id="T_PROD", slack_user_id="U_PRIMARY").first() is not None
    assert db_session.query(MemberSlack).filter_by(slack_team_id="T_PROD", slack_user_id="U_ALIAS").first() is None


def test_merge_members_reassigns_single_member_slack(client: TestClient, db_session: Session) -> None:
    """Verify when only alias has a MEMBER_SLACK record, it is cleanly reassigned to primary member."""
    seed_admin_test_data(db_session)

    # Only alias member 2 has Slack record in T_PROD
    db_session.add(MemberSlack(member_id=2, slack_team_id="T_PROD", slack_user_id="U_ALIAS_ONLY", slack_display_name="Wild Dingo"))
    db_session.commit()

    token = create_access_token(data={"sub": "admin", "role": "admin"})
    merge_res = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert merge_res.status_code == 200

    # Verify alias Slack mapping reassigned to primary member 1
    reassigned = db_session.query(MemberSlack).filter_by(slack_team_id="T_PROD", slack_user_id="U_ALIAS_ONLY").first()
    assert reassigned is not None
    assert reassigned.member_id == 1


def test_admin_endpoint_forbidden_for_non_admin_member(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/admin/aliases/requests rejects authenticated non-admin member token with 403."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.get(
        "/v2/admin/aliases/requests",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403
    assert response.json()["errorCode"] == 4003


def test_admin_endpoint_forbidden_for_token_without_role(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/admin/aliases/requests rejects token missing admin role with 403."""
    seed_admin_test_data(db_session)
    token_without_role = create_access_token(data={"sub": "user_without_role"})

    response = client.get(
        "/v2/admin/aliases/requests",
        headers={"Authorization": f"Bearer {token_without_role}"},
    )
    assert response.status_code == 403
    assert response.json()["errorCode"] == 4003


def test_admin_approve_alias_forbidden_for_non_admin_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/aliases/approve/{primary_id}/{alias_id} rejects non-admin token with 403."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.post(
        "/v2/admin/aliases/approve/1/2",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403
    assert response.json()["errorCode"] == 4003


def test_admin_direct_merge_forbidden_for_non_admin_member(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/admin/members/merge rejects non-admin member token with 403."""
    seed_admin_test_data(db_session)
    member_token = create_access_token(data={"sub": "slack:U1", "member_id": 1, "role": "member"})

    response = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403
    assert response.json()["errorCode"] == 4003


def test_moderator_role_permissions_and_restrictions(client: TestClient, db_session: Session) -> None:
    """Verify moderator can approve aliases and merge PAX, but is forbidden from managing roles."""
    seed_admin_test_data(db_session)
    admin_token = create_access_token(
        data={"sub": "U_ADMIN", "member_id": 1, "role": "admin", "roles": ["admin", "member"]}
    )

    # Admin grants 'moderator' to Member 3 (Chong Li)
    grant_res = client.post(
        "/v2/admin/members/3/roles",
        json={"role": "moderator"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert grant_res.status_code == 201
    assert grant_res.json()["role"] == "moderator"

    moderator_token = create_access_token(
        data={"sub": "U_MOD", "member_id": 3, "role": "moderator", "roles": ["moderator", "member"]}
    )

    # Moderator CAN list pending alias requests and merge members
    list_res = client.get(
        "/v2/admin/aliases/requests",
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert list_res.status_code == 200

    merge_res = client.post(
        "/v2/admin/members/merge",
        json={"primaryMemberId": 1, "aliasMemberId": 2},
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert merge_res.status_code == 200

    # Moderator CANNOT view, grant, or revoke roles (403 Forbidden)
    roles_get = client.get(
        "/v2/admin/roles",
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert roles_get.status_code == 403

    roles_post = client.post(
        "/v2/admin/members/1/roles",
        json={"role": "moderator"},
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert roles_post.status_code == 403

    roles_delete = client.delete(
        "/v2/admin/members/3/roles/moderator",
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert roles_delete.status_code == 403


