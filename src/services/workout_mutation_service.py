"""Service handling structured workout creation and deletion database mutations."""

from __future__ import annotations

import datetime
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.schemas import (
    AddWorkoutRequest,
    AOInput,
    DeleteWorkoutResponse,
    UpdateWorkoutRequest,
    WorkoutCreatedResponse,
    WorkoutUpdatedResponse,
)
from src.models.workout import (
    AO,
    Member,
    MemberAlias,
    Workout,
    WorkoutAO,
    WorkoutDetails,
    WorkoutPax,
    WorkoutQ,
)
from src.services.slack_notification_service import SlackNotificationService
from src.utils.logging import timed_service


class WorkoutMutationService:
    """Transactional creation, update, and deletion of workouts and attendee records."""

    @classmethod
    @timed_service
    def add_workout(
        cls, db: Session, data: AddWorkoutRequest, current_user: dict[str, Any] | None = None
    ) -> WorkoutCreatedResponse:
        """Add a workout directly with structured payload data."""
        parsed_date, q_names, pax_names = cls._validate_workout_input(data)

        # Pre-check for duplicate date and slug to prevent integrity conflicts
        if data.slug:
            existing = db.execute(
                select(Workout).where(
                    Workout.workout_date == parsed_date,
                    Workout.slug == data.slug,
                )
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "errorCode": 1007,
                        "errorMessage": f"A workout on {parsed_date} with slug '{data.slug}' already exists (ID: {existing.workout_id}).",
                    },
                )

        author_name = data.author or (current_user.get("f3_name") if current_user else None) or "Unknown"

        settings = get_settings()
        prefix = settings.backblast_url_prefix.rstrip("/") if settings.backblast_url_prefix else None
        resolved_url = data.url or (
            f"{prefix}/{parsed_date.strftime('%Y/%m/%d')}/{data.slug}" if (prefix and data.slug) else None
        )

        # Create and persist the WORKOUT entity
        new_workout = Workout(
            workout_date=parsed_date,
            title=data.title,
            author=author_name,
            slug=data.slug,
            backblast_url=resolved_url,
        )
        db.add(new_workout)

        try:
            db.flush()
            wid = new_workout.workout_id

            cls._save_workout_children(
                db=db,
                workout_id=wid,
                body=data.body,
                aos=data.aos,
                q_names=q_names,
                pax_names=pax_names,
            )

            db.commit()

            # Dispatch Slack Notification
            ao_names = [a.name if isinstance(a, AOInput) else str(a) for a in (data.aos if isinstance(data.aos, list) else [data.aos])]
            SlackNotificationService.post_backblast_summary(
                title=data.title,
                workout_date=str(parsed_date),
                url=resolved_url,
                author=author_name,
                aos=ao_names,
                q_names=q_names,
                pax_names=pax_names,
            )

            return WorkoutCreatedResponse(id=wid, url=resolved_url)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "errorCode": 1007,
                    "errorMessage": f"A workout on {parsed_date} with slug '{data.slug}' already exists.",
                },
            ) from None

    @classmethod
    @timed_service
    def update_workout(
        cls, db: Session, workout_id: int, data: UpdateWorkoutRequest, current_user: dict[str, Any] | None = None
    ) -> WorkoutUpdatedResponse:
        """Update/refresh an existing workout and replace its details, AOs, Qs, and PAX attendees."""
        workout = db.execute(
            select(Workout).where(Workout.workout_id == workout_id)
        ).scalar_one_or_none()

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 1001, "errorMessage": f"Workout with ID {workout_id} not found."},
            )

        # Enforce edit permissions: Admin or Original Author / Leader
        if current_user and current_user.get("role") != "admin":
            user_f3_name = current_user.get("f3_name", "").strip().lower()
            user_member_id = current_user.get("member_id")

            existing_qs = db.execute(
                select(WorkoutQ.member_id).where(WorkoutQ.workout_id == workout_id)
            ).scalars().all()

            is_author = bool(workout.author and workout.author.strip().lower() == user_f3_name)
            is_q = bool(user_member_id and user_member_id in existing_qs)

            if not (is_author or is_q):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "errorCode": 4003,
                        "errorMessage": "You are not authorized to edit this workout. Only the original author or an administrator can make changes.",
                    },
                )

        parsed_date, q_names, pax_names = cls._validate_workout_input(data)

        settings = get_settings()
        prefix = settings.backblast_url_prefix.rstrip("/") if settings.backblast_url_prefix else None
        resolved_url = data.url or (
            f"{prefix}/{parsed_date.strftime('%Y/%m/%d')}/{data.slug}" if (prefix and data.slug) else workout.backblast_url
        )

        # Update workout core entity attributes
        workout.workout_date = parsed_date
        workout.title = data.title
        if data.author:
            workout.author = data.author
        workout.slug = data.slug
        workout.backblast_url = resolved_url
        db.flush()

        # Transactionally replace child associations
        db.execute(delete(WorkoutDetails).where(WorkoutDetails.workout_id == workout_id))
        db.execute(delete(WorkoutAO).where(WorkoutAO.workout_id == workout_id))
        db.execute(delete(WorkoutQ).where(WorkoutQ.workout_id == workout_id))
        db.execute(delete(WorkoutPax).where(WorkoutPax.workout_id == workout_id))

        cls._save_workout_children(
            db=db,
            workout_id=workout_id,
            body=data.body,
            aos=data.aos,
            q_names=q_names,
            pax_names=pax_names,
        )

        db.commit()

        return WorkoutUpdatedResponse(
            id=workout_id,
            url=resolved_url,
            message="Workout updated successfully.",
        )

    @classmethod
    def _validate_workout_input(
        cls, data: AddWorkoutRequest | UpdateWorkoutRequest
    ) -> tuple[datetime.date, list[str], list[str]]:
        """Validate date format, ensure date is not in future, and validate non-empty entities."""
        parsed_date = cls._parse_date_string(data.workout_date)
        if not parsed_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 1002, "errorMessage": f"Invalid workout date format: '{data.workout_date}'."},
            )

        if parsed_date > datetime.date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 1003, "errorMessage": "Workout date cannot be in the future."},
            )

        q_names = cls._parse_name_list(data.qic)
        pax_names = cls._parse_name_list(data.pax)

        if not q_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 1004, "errorMessage": "At least one Q (leader) is required."},
            )
        if not pax_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 1005, "errorMessage": "At least one PAX attendee is required."},
            )
        if not data.aos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 1006, "errorMessage": "At least one AO is required."},
            )

        return parsed_date, q_names, pax_names

    @classmethod
    def _save_workout_children(
        cls,
        db: Session,
        workout_id: int,
        body: str | None,
        aos: list[AOInput] | list[str] | str,
        q_names: list[str],
        pax_names: list[str],
    ) -> None:
        """Persist details, AOs, Qs, and PAX attendees for a given workout ID."""
        # 1. Persist HTML content / details if provided
        if body:
            db.add(WorkoutDetails(workout_id=workout_id, html_content=body))

        # 2. Persist AOs
        ao_items: list[AOInput] = []
        if isinstance(aos, str):
            ao_items = [AOInput(name=a.strip()) for a in aos.split(",") if a.strip()]
        elif isinstance(aos, list):
            for item in aos:
                if isinstance(item, str):
                    if item.strip():
                        ao_items.append(AOInput(name=item.strip()))
                elif isinstance(item, AOInput):
                    ao_items.append(item)

        for ao_input in ao_items:
            ao_obj = cls._get_or_create_ao(db=db, ao_name=ao_input.name, ao_slug=ao_input.slug)
            db.add(WorkoutAO(workout_id=workout_id, ao_id=ao_obj.ao_id))

        # 3. Persist Qs
        for q_name in q_names:
            member = cls._get_or_create_member(db=db, name=q_name)
            db.add(WorkoutQ(workout_id=workout_id, member_id=member.member_id))

        # 4. Persist PAX Attendees
        for pax_name in pax_names:
            member = cls._get_or_create_member(db=db, name=pax_name)
            db.add(WorkoutPax(workout_id=workout_id, member_id=member.member_id))

    @classmethod
    @timed_service
    def delete_workout(cls, db: Session, workout_id: int) -> DeleteWorkoutResponse:
        """Delete a workout and all associated attendee, leader, AO, and detail records."""
        workout = db.execute(
            select(Workout).where(Workout.workout_id == workout_id)
        ).scalar_one_or_none()

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 1001, "errorMessage": f"Workout with ID {workout_id} not found."},
            )

        # Transactionally remove all child associations first
        db.execute(delete(WorkoutDetails).where(WorkoutDetails.workout_id == workout_id))
        db.execute(delete(WorkoutAO).where(WorkoutAO.workout_id == workout_id))
        db.execute(delete(WorkoutQ).where(WorkoutQ.workout_id == workout_id))
        db.execute(delete(WorkoutPax).where(WorkoutPax.workout_id == workout_id))
        db.execute(delete(Workout).where(Workout.workout_id == workout_id))
        db.commit()

        return DeleteWorkoutResponse(
            message=f"Workout {workout_id} deleted successfully.",
            workoutId=workout_id,
        )

    @classmethod
    def _parse_name_list(cls, names_input: str | list[str]) -> list[str]:
        """Convert string list or comma/conjunction delimited string to cleaned list of names."""
        if isinstance(names_input, list):
            raw_tokens = names_input
        else:
            raw_tokens = re.split(r",|\band\b|&", str(names_input), flags=re.IGNORECASE)

        cleaned_names: list[str] = []
        for token in raw_tokens:
            name = str(token).strip()
            if name and name.lower() not in ("none", "n/a", "qic", "the pax") and name not in cleaned_names:
                cleaned_names.append(name)
        return cleaned_names

    @staticmethod
    def _parse_date_string(date_str: str) -> datetime.date | None:
        """Parse varied date formats (YYYY-MM-DD, YYYYMMDD, MM/DD/YYYY, etc.)."""
        clean = str(date_str).strip()
        formats = [
            "%Y-%m-%d",
            "%Y%m%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%B %d, %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%b %d %Y",
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(clean, fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def _get_or_create_ao(cls, db: Session, ao_name: str, ao_slug: str | None = None) -> AO:
        """Find existing AO by description or create a new AO entry with provided or auto-generated slug."""
        clean_name = ao_name.strip()
        ao = db.execute(
            select(AO).where(text("UPPER(DESCRIPTION) = :d")),
            {"d": clean_name.upper()},
        ).scalar_one_or_none()

        if not ao:
            slug = ao_slug.strip() if ao_slug else clean_name.lower().replace(" ", "-").replace("'", "")
            ao = AO(description=clean_name, slug=slug)
            db.add(ao)
            db.flush()
        elif ao_slug and not ao.slug:
            ao.slug = ao_slug.strip()
            db.flush()

        return ao

    @classmethod
    def _get_or_create_member(cls, db: Session, name: str) -> Member:
        """Find existing member by primary name or alias; if not found, create a new member."""
        clean_name = name.strip()
        # 1. Check primary member name
        member = db.execute(
            select(Member).where(text("UPPER(F3_NAME) = :n")),
            {"n": clean_name.upper()},
        ).scalar_one_or_none()
        if member:
            return member

        # 2. Check alias mapping
        alias = db.execute(
            select(MemberAlias).where(text("UPPER(F3_ALIAS) = :a")),
            {"a": clean_name.upper()},
        ).scalar_one_or_none()
        if alias:
            aliased_member = db.execute(
                select(Member).where(Member.member_id == alias.member_id)
            ).scalar_one_or_none()
            if aliased_member:
                return aliased_member

        # 3. Create new member
        new_member = Member(f3_name=clean_name)
        db.add(new_member)
        db.flush()
        return new_member
