"""Service layer managing member alias claim requests, approvals, record merging, and audit trails."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.models.schemas import AliasRequestResponse, MemberSummary
from src.models.workout import (
    Member,
    MemberAlias,
    MemberAliasAudit,
    MemberAliasRequest,
    MemberSlack,
)
from src.services.email_service import EmailService
from src.utils.logging import timed_service


class AliasService:
    """Self-service alias requests, admin approval workflows, and transactional member record consolidation."""

    @classmethod
    def _get_member_email(cls, db: Session, member_id: int) -> str | None:
        """Retrieve the most recently updated Slack email address for a member if available."""
        slack_record = (
            db.execute(
                select(MemberSlack)
                .where(
                    MemberSlack.member_id == member_id,
                    MemberSlack.slack_email.is_not(None),
                )
                .order_by(MemberSlack.updated_at.desc())
            )
            .scalars()
            .first()
        )
        if slack_record and slack_record.slack_email:
            cleaned = slack_record.slack_email.strip()
            return cleaned if cleaned else None
        return None

    @classmethod
    @timed_service
    def request_alias(
        cls, db: Session, primary_id: int, alias_id: int
    ) -> AliasRequestResponse:
        """Submit a request to claim an alias name for a primary member."""
        if primary_id == alias_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 2003, "errorMessage": "Primary member and alias member cannot be the same."},
            )

        primary = db.execute(select(Member).where(Member.member_id == primary_id)).scalar_one_or_none()
        alias_member = db.execute(select(Member).where(Member.member_id == alias_id)).scalar_one_or_none()

        if not primary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 2001, "errorMessage": f"Primary member with ID {primary_id} not found."},
            )
        if not alias_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 2001, "errorMessage": f"Alias member with ID {alias_id} not found."},
            )

        # Check for existing pending request
        existing_req = db.execute(
            select(MemberAliasRequest).where(
                MemberAliasRequest.primary_id == primary_id,
                MemberAliasRequest.alias_id == alias_id,
                MemberAliasRequest.status == "pending",
            )
        ).scalar_one_or_none()

        if existing_req:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"errorCode": 2004, "errorMessage": "A pending alias request already exists for these members."},
            )

        new_req = MemberAliasRequest(primary_id=primary_id, alias_id=alias_id, status="pending")
        db.add(new_req)
        db.commit()

        primary_summary = MemberSummary(memberId=primary.member_id, f3Name=primary.f3_name)
        alias_summary = MemberSummary(memberId=alias_member.member_id, f3Name=alias_member.f3_name)

        requestor_email = cls._get_member_email(db, primary_id)
        EmailService.send_alias_request_admin_notification(
            primary_member=primary_summary,
            alias_member=alias_summary,
            requestor_email=requestor_email,
        )
        if requestor_email:
            EmailService.send_alias_request_receipt_notification(
                primary_member=primary_summary,
                alias_member=alias_summary,
                recipient_email=requestor_email,
            )

        return AliasRequestResponse(
            primaryMember=primary_summary,
            aliasMember=alias_summary,
            status=new_req.status,
        )

    @classmethod
    @timed_service
    def get_pending_requests(cls, db: Session) -> list[AliasRequestResponse]:
        """Retrieve all pending alias requests matching MySQL MEMBER_ALIAS_REQUEST schema."""
        query = text(
            """
            SELECT
                mar.STATUS,
                m1.MEMBER_ID AS PRIMARY_ID,
                m1.F3_NAME AS PRIMARY_NAME,
                m2.MEMBER_ID AS ALIAS_ID,
                m2.F3_NAME AS ALIAS_NAME
            FROM MEMBER_ALIAS_REQUEST mar
            INNER JOIN MEMBER m1 ON mar.PRIMARY_ID = m1.MEMBER_ID
            INNER JOIN MEMBER m2 ON mar.ALIAS_ID = m2.MEMBER_ID
            WHERE mar.STATUS = 'pending'
            ORDER BY m1.F3_NAME ASC
            """
        )
        rows = db.execute(query).mappings().all()
        return [
            AliasRequestResponse(
                primaryMember=MemberSummary(memberId=r["PRIMARY_ID"], f3Name=r["PRIMARY_NAME"]),
                aliasMember=MemberSummary(memberId=r["ALIAS_ID"], f3Name=r["ALIAS_NAME"]),
                status=r["STATUS"],
            )
            for r in rows
        ]

    @classmethod
    def _transition_request_status(
        cls, db: Session, primary_id: int, alias_id: int, new_status: str
    ) -> None:
        """Transition a pending alias request to new_status, removing any prior row with the same target status."""
        db.execute(
            text(
                "DELETE FROM MEMBER_ALIAS_REQUEST "
                "WHERE PRIMARY_ID = :p AND ALIAS_ID = :a AND STATUS = :target_status"
            ),
            {"p": primary_id, "a": alias_id, "target_status": new_status},
        )
        db.execute(
            text(
                "UPDATE MEMBER_ALIAS_REQUEST SET STATUS = :target_status "
                "WHERE PRIMARY_ID = :p AND ALIAS_ID = :a AND STATUS = 'pending'"
            ),
            {"p": primary_id, "a": alias_id, "target_status": new_status},
        )

    @classmethod
    @timed_service
    def approve_alias(cls, db: Session, primary_id: int, alias_id: int) -> AliasRequestResponse:
        """Approve alias request: reassign workouts, generate audit trail, register alias, and delete duplicate member."""
        pending_req = db.execute(
            select(MemberAliasRequest).where(
                MemberAliasRequest.primary_id == primary_id,
                MemberAliasRequest.alias_id == alias_id,
                MemberAliasRequest.status == "pending",
            )
        ).scalar_one_or_none()

        if not pending_req:
            existing_any = (
                db.execute(
                    select(MemberAliasRequest).where(
                        MemberAliasRequest.primary_id == primary_id,
                        MemberAliasRequest.alias_id == alias_id,
                    )
                )
                .scalars()
                .first()
            )
            if not existing_any:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"errorCode": 2005, "errorMessage": f"Alias request for primary {primary_id} and alias {alias_id} not found."},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 2006, "errorMessage": f"Alias request is already {existing_any.status}."},
            )

        res = cls._execute_member_merge(db=db, primary_id=primary_id, alias_id=alias_id)
        cls._transition_request_status(db, primary_id, alias_id, "approved")
        db.commit()

        requestor_email = cls._get_member_email(db, primary_id)
        if requestor_email:
            EmailService.send_alias_approved_notification(
                primary_member=res.primary_member,
                alias_member=res.alias_member,
                recipient_email=requestor_email,
            )

        return res

    @classmethod
    @timed_service
    def direct_merge(cls, db: Session, primary_id: int, alias_id: int) -> AliasRequestResponse:
        """Directly merge two members by an admin without requiring a prior pending request."""
        res = cls._execute_member_merge(db=db, primary_id=primary_id, alias_id=alias_id)
        # If a pending request happened to exist for them, mark it approved
        pending_req = db.execute(
            select(MemberAliasRequest).where(
                MemberAliasRequest.primary_id == primary_id,
                MemberAliasRequest.alias_id == alias_id,
                MemberAliasRequest.status == "pending",
            )
        ).scalar_one_or_none()
        if pending_req:
            cls._transition_request_status(db, primary_id, alias_id, "approved")
        db.commit()
        return res

    @classmethod
    def _execute_member_merge(cls, db: Session, primary_id: int, alias_id: int) -> AliasRequestResponse:
        """Internal helper to atomically merge attendance records, generate audit trails, and delete duplicate member."""
        if primary_id == alias_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 2003, "errorMessage": "Primary member and alias member cannot be the same."},
            )

        primary = db.execute(select(Member).where(Member.member_id == primary_id)).scalar_one_or_none()
        alias_member = db.execute(select(Member).where(Member.member_id == alias_id)).scalar_one_or_none()

        if not primary or not alias_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 2001, "errorMessage": "One or more members in this merge request do not exist."},
            )

        alias_name = alias_member.f3_name

        # 1. Audit Trail: log all PAX and Q records prior to merge
        pax_workouts = db.execute(
            text("SELECT WORKOUT_ID FROM WORKOUT_PAX WHERE MEMBER_ID = :m"), {"m": alias_id}
        ).scalars().all()
        for wid in pax_workouts:
            db.add(
                MemberAliasAudit(
                    old_member_id=alias_id,
                    old_f3_name=alias_name,
                    workout_id=wid,
                    member_type="PAX",
                )
            )

        q_workouts = db.execute(
            text("SELECT WORKOUT_ID FROM WORKOUT_Q WHERE MEMBER_ID = :m"), {"m": alias_id}
        ).scalars().all()
        for wid in q_workouts:
            db.add(
                MemberAliasAudit(
                    old_member_id=alias_id,
                    old_f3_name=alias_name,
                    workout_id=wid,
                    member_type="Q",
                )
            )
        db.flush()

        # 2. Relink WORKOUT_PAX (avoid duplicate primary in same workout)
        for wid in pax_workouts:
            already_attending = db.execute(
                text("SELECT 1 FROM WORKOUT_PAX WHERE WORKOUT_ID = :w AND MEMBER_ID = :p"),
                {"w": wid, "p": primary_id},
            ).scalar()
            if already_attending:
                db.execute(
                    text("DELETE FROM WORKOUT_PAX WHERE WORKOUT_ID = :w AND MEMBER_ID = :a"),
                    {"w": wid, "a": alias_id},
                )
            else:
                db.execute(
                    text("UPDATE WORKOUT_PAX SET MEMBER_ID = :p WHERE WORKOUT_ID = :w AND MEMBER_ID = :a"),
                    {"p": primary_id, "w": wid, "a": alias_id},
                )

        # 3. Relink WORKOUT_Q (avoid duplicate Q in same workout)
        for wid in q_workouts:
            already_q = db.execute(
                text("SELECT 1 FROM WORKOUT_Q WHERE WORKOUT_ID = :w AND MEMBER_ID = :p"),
                {"w": wid, "p": primary_id},
            ).scalar()
            if already_q:
                db.execute(
                    text("DELETE FROM WORKOUT_Q WHERE WORKOUT_ID = :w AND MEMBER_ID = :a"),
                    {"w": wid, "a": alias_id},
                )
            else:
                db.execute(
                    text("UPDATE WORKOUT_Q SET MEMBER_ID = :p WHERE WORKOUT_ID = :w AND MEMBER_ID = :a"),
                    {"p": primary_id, "w": wid, "a": alias_id},
                )

        # 4. Relink existing aliases of alias_id to primary_id
        db.execute(
            text("UPDATE MEMBER_ALIAS SET MEMBER_ID = :p WHERE MEMBER_ID = :a"),
            {"p": primary_id, "a": alias_id},
        )

        # 5. Insert new alias mapping for primary_id -> alias_name
        existing_alias_map = db.execute(
            select(MemberAlias).where(
                MemberAlias.member_id == primary_id,
                MemberAlias.f3_alias == alias_name,
            )
        ).scalar_one_or_none()
        if not existing_alias_map:
            db.add(MemberAlias(member_id=primary_id, f3_alias=alias_name))

        # 6. Handle MEMBER_SLACK mapping merge
        alias_slacks = db.execute(
            select(MemberSlack).where(MemberSlack.member_id == alias_id)
        ).scalars().all()
        for a_slack in alias_slacks:
            primary_slack = db.execute(
                select(MemberSlack).where(
                    MemberSlack.member_id == primary_id,
                    MemberSlack.slack_team_id == a_slack.slack_team_id,
                )
            ).scalar_one_or_none()
            if primary_slack:
                # If primary already has a mapping for this team, delete the alias mapping
                db.delete(a_slack)
            else:
                # Otherwise reassign alias mapping to primary member
                a_slack.member_id = primary_id
        db.flush()

        # 7. Delete the duplicate member entity
        db.delete(alias_member)
        db.flush()

        return AliasRequestResponse(
            primaryMember=MemberSummary(memberId=primary.member_id, f3Name=primary.f3_name),
            aliasMember=MemberSummary(memberId=alias_id, f3Name=alias_name),
            status="approved",
        )

    @classmethod
    @timed_service
    def reject_alias(cls, db: Session, primary_id: int, alias_id: int) -> AliasRequestResponse:
        """Reject a pending alias request."""
        pending_req = db.execute(
            select(MemberAliasRequest).where(
                MemberAliasRequest.primary_id == primary_id,
                MemberAliasRequest.alias_id == alias_id,
                MemberAliasRequest.status == "pending",
            )
        ).scalar_one_or_none()

        if not pending_req:
            existing_any = (
                db.execute(
                    select(MemberAliasRequest).where(
                        MemberAliasRequest.primary_id == primary_id,
                        MemberAliasRequest.alias_id == alias_id,
                    )
                )
                .scalars()
                .first()
            )
            if not existing_any:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"errorCode": 2005, "errorMessage": f"Alias request for primary {primary_id} and alias {alias_id} not found."},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 2006, "errorMessage": f"Alias request is already {existing_any.status}."},
            )

        cls._transition_request_status(db, primary_id, alias_id, "rejected")
        db.commit()

        primary = db.execute(select(Member).where(Member.member_id == primary_id)).scalar_one_or_none()
        alias_member = db.execute(select(Member).where(Member.member_id == alias_id)).scalar_one_or_none()

        primary_summary = MemberSummary(
            memberId=primary_id, f3Name=primary.f3_name if primary else f"Member {primary_id}"
        )
        alias_summary = MemberSummary(
            memberId=alias_id, f3Name=alias_member.f3_name if alias_member else f"Member {alias_id}"
        )

        requestor_email = cls._get_member_email(db, primary_id)
        if requestor_email:
            EmailService.send_alias_rejected_notification(
                primary_member=primary_summary,
                alias_member=alias_summary,
                recipient_email=requestor_email,
            )

        return AliasRequestResponse(
            primaryMember=primary_summary,
            aliasMember=alias_summary,
            status="rejected",
        )
