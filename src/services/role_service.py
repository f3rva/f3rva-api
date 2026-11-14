"""Service layer managing Role-Based Access Control (RBAC) assignments in MEMBER_ROLE."""

from __future__ import annotations

import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.models.schemas import MemberRoleAssignmentResponse, RevokeMemberRoleResponse
from src.models.workout import Member, MemberRole, MemberSlack
from src.utils.logging import timed_service

ALLOWED_ROLES: frozenset[str] = frozenset({"admin"})


class RoleService:
    """Business logic for listing, granting, and revoking member roles."""

    @classmethod
    @timed_service
    def get_role_assignments(cls, db: Session) -> list[MemberRoleAssignmentResponse]:
        """Retrieve all active role assignments from MEMBER_ROLE joined with member metadata."""
        query = text(
            """
            SELECT
                mr.MEMBER_ID,
                m.F3_NAME,
                mr.ROLE,
                mr.GRANTED_BY,
                gm.F3_NAME AS GRANTED_BY_NAME,
                mr.CREATED_AT,
                (
                    SELECT ms.SLACK_DISPLAY_NAME
                    FROM MEMBER_SLACK ms
                    WHERE ms.MEMBER_ID = mr.MEMBER_ID
                    ORDER BY ms.UPDATED_AT DESC
                    LIMIT 1
                ) AS SLACK_DISPLAY_NAME
            FROM MEMBER_ROLE mr
            INNER JOIN MEMBER m ON mr.MEMBER_ID = m.MEMBER_ID
            LEFT JOIN MEMBER gm ON mr.GRANTED_BY = gm.MEMBER_ID
            ORDER BY m.F3_NAME ASC, mr.ROLE ASC
            """
        )
        rows = db.execute(query).mappings().all()
        results: list[MemberRoleAssignmentResponse] = []
        for r in rows:
            raw_created = r["CREATED_AT"]
            created_str = (
                raw_created.isoformat()
                if isinstance(raw_created, datetime.datetime)
                else (str(raw_created) if raw_created is not None else None)
            )
            results.append(
                MemberRoleAssignmentResponse(
                    memberId=int(r["MEMBER_ID"]),
                    f3Name=str(r["F3_NAME"]),
                    slackDisplayName=r["SLACK_DISPLAY_NAME"],
                    role=str(r["ROLE"]),
                    grantedByMemberId=int(r["GRANTED_BY"]) if r["GRANTED_BY"] is not None else None,
                    grantedByF3Name=r["GRANTED_BY_NAME"],
                    createdAt=created_str,
                )
            )
        return results

    @classmethod
    @timed_service
    def grant_role(
        cls,
        db: Session,
        member_id: int,
        role: str,
        granted_by_member_id: int | None = None,
    ) -> MemberRoleAssignmentResponse:
        """Grant an access control role to a member idempotently."""
        normalized_role = role.strip().lower()
        if normalized_role not in ALLOWED_ROLES:
            allowed_list = ", ".join(sorted(ALLOWED_ROLES))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": 4004,
                    "errorMessage": f"Invalid role '{role}'. Allowed roles: {allowed_list}.",
                },
            )

        member = db.execute(
            select(Member).where(Member.member_id == member_id)
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 2001, "errorMessage": f"Member with ID {member_id} not found."},
            )

        valid_grantor_id: int | None = None
        grantor_name: str | None = None
        if granted_by_member_id is not None:
            grantor = db.execute(
                select(Member).where(Member.member_id == int(granted_by_member_id))
            ).scalar_one_or_none()
            if grantor:
                valid_grantor_id = grantor.member_id
                grantor_name = grantor.f3_name

        existing = db.execute(
            select(MemberRole).where(
                MemberRole.member_id == member_id,
                MemberRole.role == normalized_role,
            )
        ).scalar_one_or_none()

        if not existing:
            now = datetime.datetime.now(datetime.UTC)
            existing = MemberRole(
                member_id=member_id,
                role=normalized_role,
                granted_by=valid_grantor_id,
                created_at=now,
            )
            db.add(existing)
            db.commit()
        elif existing.granted_by and not grantor_name:
            prior_grantor = db.execute(
                select(Member).where(Member.member_id == existing.granted_by)
            ).scalar_one_or_none()
            if prior_grantor:
                grantor_name = prior_grantor.f3_name

        slack_rec = (
            db.execute(
                select(MemberSlack)
                .where(MemberSlack.member_id == member_id)
                .order_by(MemberSlack.updated_at.desc())
            )
            .scalars()
            .first()
        )

        created_str = (
            existing.created_at.isoformat()
            if isinstance(existing.created_at, datetime.datetime)
            else (str(existing.created_at) if existing.created_at is not None else None)
        )

        return MemberRoleAssignmentResponse(
            memberId=member.member_id,
            f3Name=member.f3_name,
            slackDisplayName=slack_rec.slack_display_name if slack_rec else None,
            role=normalized_role,
            grantedByMemberId=existing.granted_by,
            grantedByF3Name=grantor_name,
            createdAt=created_str,
        )

    @classmethod
    @timed_service
    def revoke_role(
        cls,
        db: Session,
        member_id: int,
        role: str,
        acting_member_id: int | None = None,
    ) -> RevokeMemberRoleResponse:
        """Revoke an access control role from a member, preventing self-lockout."""
        normalized_role = role.strip().lower()

        if acting_member_id is not None and int(acting_member_id) == int(member_id) and normalized_role == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": 4005,
                    "errorMessage": "You cannot revoke your own administrator role.",
                },
            )

        assignment = db.execute(
            select(MemberRole).where(
                MemberRole.member_id == member_id,
                MemberRole.role == normalized_role,
            )
        ).scalar_one_or_none()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "errorCode": 4006,
                    "errorMessage": f"Role '{normalized_role}' is not assigned to member ID {member_id}.",
                },
            )

        db.delete(assignment)
        db.commit()

        return RevokeMemberRoleResponse(
            message=f"Role '{normalized_role}' revoked from member ID {member_id}.",
            memberId=member_id,
            role=normalized_role,
        )
