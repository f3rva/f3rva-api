"""Service layer for F3 member lookups, profiles, alias associations, and attendance analytics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from src.models.schemas import (
    AOSummary,
    MemberDetailResponse,
    MemberStatsResponse,
    MemberSummary,
    WorkoutResponse,
)
from src.utils.logging import timed_service


class MemberService:
    """Member business logic, profile aggregation, and attendance statistics."""

    @classmethod
    @timed_service
    def get_all_members(cls, db: Session) -> list[MemberSummary]:
        """Retrieve an alphabetical list of all registered F3 members."""
        query = text(
            """
            SELECT MEMBER_ID, F3_NAME
            FROM MEMBER
            ORDER BY F3_NAME ASC
            """
        )
        rows = db.execute(query).mappings().all()
        return [MemberSummary(memberId=r["MEMBER_ID"], f3Name=r["F3_NAME"]) for r in rows]

    @classmethod
    @timed_service
    def get_member_stats(cls, db: Session, member_id: int) -> MemberStatsResponse | None:
        """Calculate total workouts attended, total Qs led, and the calculated Q-ratio."""
        member_check = db.execute(
            text("SELECT MEMBER_ID FROM MEMBER WHERE MEMBER_ID = :member_id"),
            {"member_id": member_id},
        ).scalar()
        if not member_check:
            return None

        stats_query = text(
            """
            SELECT
                (SELECT COUNT(*) FROM WORKOUT_PAX WHERE MEMBER_ID = :member_id) AS NUM_WORKOUTS,
                (SELECT COUNT(*) FROM WORKOUT_Q WHERE MEMBER_ID = :member_id) AS NUM_QS
            """
        )
        row = db.execute(stats_query, {"member_id": member_id}).mappings().first()
        num_workouts = row["NUM_WORKOUTS"] if row else 0
        num_qs = row["NUM_QS"] if row else 0
        q_ratio = round(num_qs / num_workouts, 4) if num_workouts > 0 else 0.0

        return MemberStatsResponse(
            memberId=member_id,
            numWorkouts=num_workouts,
            numQs=num_qs,
            qRatio=q_ratio,
        )

    @classmethod
    @timed_service
    def get_member_by_id(cls, db: Session, member_id: int) -> MemberDetailResponse | None:
        """Retrieve full member profile including aliases, statistics, and workout history."""
        member_query = text(
            """
            SELECT MEMBER_ID, F3_NAME
            FROM MEMBER
            WHERE MEMBER_ID = :member_id
            """
        )
        member_row = db.execute(member_query, {"member_id": member_id}).mappings().first()
        if not member_row:
            return None

        # 1. Retrieve registered aliases
        alias_query = text(
            """
            SELECT F3_ALIAS
            FROM MEMBER_ALIAS
            WHERE MEMBER_ID = :member_id
            ORDER BY F3_ALIAS ASC
            """
        )
        alias_rows = db.execute(alias_query, {"member_id": member_id}).scalars().all()
        aliases = list(alias_rows)

        # 2. Retrieve stats
        stats = cls.get_member_stats(db=db, member_id=member_id)

        # 3. Retrieve attended workouts (as PAX)
        pax_workouts_query = text(
            """
            SELECT
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL,
                GROUP_CONCAT(DISTINCT ao.AO_ID) AS AO_IDS,
                GROUP_CONCAT(DISTINCT ao.DESCRIPTION) AS AO_DESCRIPTIONS,
                GROUP_CONCAT(DISTINCT ao.SLUG) AS AO_SLUGS,
                GROUP_CONCAT(DISTINCT mq.MEMBER_ID) AS Q_IDS,
                GROUP_CONCAT(DISTINCT mq.F3_NAME) AS Q_NAMES,
                COUNT(DISTINCT wp_all.MEMBER_ID) AS PAX_COUNT
            FROM (
                SELECT w_inner.WORKOUT_ID, w_inner.WORKOUT_DATE, w_inner.TITLE, w_inner.AUTHOR, w_inner.SLUG, w_inner.BACKBLAST_URL
                FROM WORKOUT w_inner
                INNER JOIN WORKOUT_PAX wp ON w_inner.WORKOUT_ID = wp.WORKOUT_ID
                WHERE wp.MEMBER_ID = :member_id
                ORDER BY w_inner.WORKOUT_DATE DESC, w_inner.WORKOUT_ID DESC
            ) w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_PAX wp_all ON w.WORKOUT_ID = wp_all.WORKOUT_ID
            GROUP BY
                w.WORKOUT_ID, w.WORKOUT_DATE, w.TITLE, w.AUTHOR, w.SLUG, w.BACKBLAST_URL
            ORDER BY
                w.WORKOUT_DATE DESC, AO_DESCRIPTIONS ASC
            """
        )
        pax_rows = db.execute(pax_workouts_query, {"member_id": member_id}).mappings().all()
        attended_workouts = [cls._map_row_to_workout(r) for r in pax_rows]

        # 4. Retrieve Q'd workouts (as Leader)
        q_workouts_query = text(
            """
            SELECT
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL,
                GROUP_CONCAT(DISTINCT ao.AO_ID) AS AO_IDS,
                GROUP_CONCAT(DISTINCT ao.DESCRIPTION) AS AO_DESCRIPTIONS,
                GROUP_CONCAT(DISTINCT ao.SLUG) AS AO_SLUGS,
                GROUP_CONCAT(DISTINCT mq.MEMBER_ID) AS Q_IDS,
                GROUP_CONCAT(DISTINCT mq.F3_NAME) AS Q_NAMES,
                COUNT(DISTINCT wp_all.MEMBER_ID) AS PAX_COUNT
            FROM (
                SELECT w_inner.WORKOUT_ID, w_inner.WORKOUT_DATE, w_inner.TITLE, w_inner.AUTHOR, w_inner.SLUG, w_inner.BACKBLAST_URL
                FROM WORKOUT w_inner
                INNER JOIN WORKOUT_Q wq_filter ON w_inner.WORKOUT_ID = wq_filter.WORKOUT_ID
                WHERE wq_filter.MEMBER_ID = :member_id
                ORDER BY w_inner.WORKOUT_DATE DESC, w_inner.WORKOUT_ID DESC
            ) w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_PAX wp_all ON w.WORKOUT_ID = wp_all.WORKOUT_ID
            GROUP BY
                w.WORKOUT_ID, w.WORKOUT_DATE, w.TITLE, w.AUTHOR, w.SLUG, w.BACKBLAST_URL
            ORDER BY
                w.WORKOUT_DATE DESC, AO_DESCRIPTIONS ASC
            """
        )
        q_rows = db.execute(q_workouts_query, {"member_id": member_id}).mappings().all()
        qd_workouts = [cls._map_row_to_workout(r) for r in q_rows]

        return MemberDetailResponse(
            memberId=member_row["MEMBER_ID"],
            f3Name=member_row["F3_NAME"],
            aliases=aliases,
            stats=stats,
            attendedWorkouts=attended_workouts,
            qdWorkouts=qd_workouts,
        )

    @classmethod
    @timed_service
    def lookup_members(cls, db: Session, query_str: str) -> list[MemberSummary]:
        """Case-insensitive member search across both primary F3 names and registered aliases."""
        clean_query = query_str.strip()
        if not clean_query:
            return []

        search_param = f"%{clean_query}%"
        query = text(
            """
            SELECT DISTINCT m.MEMBER_ID, m.F3_NAME
            FROM MEMBER m
            LEFT OUTER JOIN MEMBER_ALIAS ma ON m.MEMBER_ID = ma.MEMBER_ID
            WHERE UPPER(m.F3_NAME) LIKE UPPER(:search_param)
               OR UPPER(ma.F3_ALIAS) LIKE UPPER(:search_param)
            ORDER BY m.F3_NAME ASC
            """
        )
        rows = db.execute(query, {"search_param": search_param}).mappings().all()
        return [MemberSummary(memberId=r["MEMBER_ID"], f3Name=r["F3_NAME"]) for r in rows]

    @staticmethod
    def _map_row_to_workout(row: RowMapping | Mapping[Any, Any]) -> WorkoutResponse:
        """Map raw database row mapping to strongly-typed WorkoutResponse DTO."""
        ao_list: list[AOSummary] = []
        ao_ids_raw = row.get("AO_IDS")
        ao_descs_raw = row.get("AO_DESCRIPTIONS")
        ao_slugs_raw = row.get("AO_SLUGS")

        if ao_descs_raw:
            ao_ids = [int(i.strip()) for i in str(ao_ids_raw).split(",") if i.strip().isdigit()]
            ao_descs = [d.strip() for d in str(ao_descs_raw).split(",") if d.strip()]
            ao_slugs = (
                [s.strip() for s in str(ao_slugs_raw).split(",")] if ao_slugs_raw else []
            )

            for idx, desc in enumerate(ao_descs):
                ao_id = ao_ids[idx] if idx < len(ao_ids) else None
                ao_slug = ao_slugs[idx] if idx < len(ao_slugs) else None
                ao_list.append(AOSummary(id=ao_id, description=desc, slug=ao_slug))

        q_list: list[MemberSummary] = []
        q_ids_raw = row.get("Q_IDS")
        q_names_raw = row.get("Q_NAMES")

        if q_names_raw:
            q_ids = [int(i.strip()) for i in str(q_ids_raw).split(",") if i.strip().isdigit()]
            q_names = [n.strip() for n in str(q_names_raw).split(",") if n.strip()]

            for idx, name in enumerate(q_names):
                q_id = q_ids[idx] if idx < len(q_ids) else 0
                q_list.append(MemberSummary(memberId=q_id, f3Name=name))

        workout_date_val = row["WORKOUT_DATE"]
        workout_date_str = (
            workout_date_val.strftime("%Y-%m-%d")
            if hasattr(workout_date_val, "strftime")
            else str(workout_date_val)
        )

        return WorkoutResponse(
            workoutId=row["WORKOUT_ID"],
            backblastUrl=row.get("BACKBLAST_URL"),
            title=row["TITLE"],
            author=row.get("AUTHOR"),
            slug=row.get("SLUG"),
            ao=ao_list,
            q=q_list,
            paxCount=row.get("PAX_COUNT") or 0,
            workoutDate=workout_date_str,
            content=None,
        )
