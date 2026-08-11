"""SQLAlchemy ORM Data Models for Workouts, AOs, PAX, and Alias Requests."""

from __future__ import annotations

import datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class AO(Base):
    """Area of Operations (AO) database entity."""

    __tablename__ = "AO"

    ao_id: Mapped[int] = mapped_column("AO_ID", Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column("DESCRIPTION", String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column("SLUG", String(255), nullable=True)


class Member(Base):
    """F3 Member database entity."""

    __tablename__ = "MEMBER"

    member_id: Mapped[int] = mapped_column(
        "MEMBER_ID", Integer, primary_key=True, autoincrement=True
    )
    f3_name: Mapped[str] = mapped_column("F3_NAME", String(255), nullable=False)


class MemberAlias(Base):
    """Member Alias database entity."""

    __tablename__ = "MEMBER_ALIAS"

    member_id: Mapped[int] = mapped_column(
        "MEMBER_ID", Integer, ForeignKey("MEMBER.MEMBER_ID"), primary_key=True
    )
    f3_alias: Mapped[str] = mapped_column("F3_ALIAS", String(255), primary_key=True)


class MemberAliasRequest(Base):
    """Member Alias Claim Request entity using composite primary key (PRIMARY_ID, ALIAS_ID)."""

    __tablename__ = "MEMBER_ALIAS_REQUEST"

    primary_id: Mapped[int] = mapped_column(
        "PRIMARY_ID", Integer, ForeignKey("MEMBER.MEMBER_ID"), primary_key=True
    )
    alias_id: Mapped[int] = mapped_column(
        "ALIAS_ID", Integer, ForeignKey("MEMBER.MEMBER_ID"), primary_key=True
    )
    status: Mapped[str] = mapped_column("STATUS", String(32), default="pending", nullable=False)


class MemberAliasAudit(Base):
    """Audit trail for merged member records."""

    __tablename__ = "MEMBER_ALIAS_AUDIT"

    audit_id: Mapped[int] = mapped_column(
        "AUDIT_ID", Integer, primary_key=True, autoincrement=True
    )
    old_member_id: Mapped[int] = mapped_column("OLD_MEMBER_ID", Integer, nullable=False)
    old_f3_name: Mapped[str] = mapped_column("OLD_F3_NAME", String(255), nullable=False)
    workout_id: Mapped[int] = mapped_column("WORKOUT_ID", Integer, nullable=False)
    member_type: Mapped[str] = mapped_column("MEMBER_TYPE", String(32), nullable=False)


class Workout(Base):
    """Workout backblast database entity."""

    __tablename__ = "WORKOUT"

    workout_id: Mapped[int] = mapped_column(
        "WORKOUT_ID", Integer, primary_key=True, autoincrement=True
    )
    workout_date: Mapped[datetime.date] = mapped_column("WORKOUT_DATE", Date, nullable=False)
    title: Mapped[str] = mapped_column("TITLE", String(255), nullable=False)
    author: Mapped[str | None] = mapped_column("AUTHOR", String(255), nullable=True)
    slug: Mapped[str | None] = mapped_column("SLUG", String(255), nullable=True)
    backblast_url: Mapped[str | None] = mapped_column("BACKBLAST_URL", String(512), nullable=True)


class WorkoutAO(Base):
    """Many-to-many relationship mapping Workouts to AOs."""

    __tablename__ = "WORKOUT_AO"

    workout_id: Mapped[int] = mapped_column(
        "WORKOUT_ID", Integer, ForeignKey("WORKOUT.WORKOUT_ID"), primary_key=True
    )
    ao_id: Mapped[int] = mapped_column(
        "AO_ID", Integer, ForeignKey("AO.AO_ID"), primary_key=True
    )


class WorkoutQ(Base):
    """Many-to-many relationship mapping Workouts to Workout Leaders (Qs)."""

    __tablename__ = "WORKOUT_Q"

    workout_id: Mapped[int] = mapped_column(
        "WORKOUT_ID", Integer, ForeignKey("WORKOUT.WORKOUT_ID"), primary_key=True
    )
    member_id: Mapped[int] = mapped_column(
        "MEMBER_ID", Integer, ForeignKey("MEMBER.MEMBER_ID"), primary_key=True
    )


class WorkoutPax(Base):
    """Many-to-many relationship mapping Workouts to Attendees (PAX)."""

    __tablename__ = "WORKOUT_PAX"

    workout_id: Mapped[int] = mapped_column(
        "WORKOUT_ID", Integer, ForeignKey("WORKOUT.WORKOUT_ID"), primary_key=True
    )
    member_id: Mapped[int] = mapped_column(
        "MEMBER_ID", Integer, ForeignKey("MEMBER.MEMBER_ID"), primary_key=True
    )


class WorkoutDetails(Base):
    """1:1 metadata and scraped HTML content for workouts."""

    __tablename__ = "WORKOUT_DETAILS"

    workout_id: Mapped[int] = mapped_column(
        "WORKOUT_ID", Integer, ForeignKey("WORKOUT.WORKOUT_ID"), primary_key=True
    )
    html_content: Mapped[str | None] = mapped_column("HTML_CONTENT", Text, nullable=True)
