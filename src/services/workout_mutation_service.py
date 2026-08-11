"""Service handling structured workout creation and deletion database mutations."""

from __future__ import annotations

import datetime
import re

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from src.models.schemas import (
    AddWorkoutRequest,
    AOInput,
    DeleteWorkoutResponse,
    WorkoutCreatedResponse,
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
from src.utils.logging import timed_service


class WorkoutMutationService:
    """Transactional creation and deletion of workouts and attendee records."""

    @classmethod
    @timed_service
    def add_workout(cls, db: Session, data: AddWorkoutRequest) -> WorkoutCreatedResponse:
        """Add a workout directly with structured payload data."""
        # 1. Parse and validate workout date
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

        # 2. Parse Qs, PAX, and AOs
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

        # 3. Create and persist the WORKOUT entity
        new_workout = Workout(
            workout_date=parsed_date,
            title=data.title,
            author=data.author,
            slug=data.slug,
            backblast_url=data.url,
        )
        db.add(new_workout)
        db.flush()

        wid = new_workout.workout_id

        # 4. Persist HTML content / details if provided
        if data.body:
            db.add(WorkoutDetails(workout_id=wid, html_content=data.body))

        # 5. Persist AOs
        ao_items: list[AOInput] = []
        if isinstance(data.aos, str):
            ao_items = [AOInput(name=a.strip()) for a in data.aos.split(",") if a.strip()]
        elif isinstance(data.aos, list):
            for item in data.aos:
                if isinstance(item, str):
                    if item.strip():
                        ao_items.append(AOInput(name=item.strip()))
                elif isinstance(item, AOInput):
                    ao_items.append(item)

        for ao_input in ao_items:
            ao_obj = cls._get_or_create_ao(db=db, ao_name=ao_input.name, ao_slug=ao_input.slug)
            db.add(WorkoutAO(workout_id=wid, ao_id=ao_obj.ao_id))

        # 6. Persist Qs
        for q_name in q_names:
            member = cls._get_or_create_member(db=db, name=q_name)
            db.add(WorkoutQ(workout_id=wid, member_id=member.member_id))

        # 7. Persist PAX Attendees
        for pax_name in pax_names:
            member = cls._get_or_create_member(db=db, name=pax_name)
            db.add(WorkoutPax(workout_id=wid, member_id=member.member_id))

        db.commit()
        return WorkoutCreatedResponse(id=wid)

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
