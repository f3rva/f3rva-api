"""Service layer encapsulating workout queries, pagination, and data transformations."""

from __future__ import annotations

import calendar
import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.schemas import AOSummary, MemberSummary, WorkoutResponse
from src.utils.logging import timed_service


class WorkoutService:
    """Workout business logic, date calculations, and repository queries."""

    @staticmethod
    def get_offset(page: int, page_size: int) -> int:
        """Calculate SQL offset from 1-based page and page_size."""
        return max(0, (page - 1) * page_size)

    @classmethod
    @timed_service
    def get_recent_workouts(
        cls, db: Session, page: int = 1, page_size: int = 20
    ) -> list[WorkoutResponse]:
        """Retrieve paginated recent workouts ordered by date descending using optimized derived table pagination."""
        offset = cls.get_offset(page, page_size)
        query = text(
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
                COUNT(DISTINCT wp.MEMBER_ID) AS PAX_COUNT
            FROM (
                SELECT WORKOUT_ID, WORKOUT_DATE, TITLE, AUTHOR, SLUG, BACKBLAST_URL
                FROM WORKOUT
                ORDER BY WORKOUT_DATE DESC, WORKOUT_ID DESC
                LIMIT :limit OFFSET :offset
            ) w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_PAX wp ON w.WORKOUT_ID = wp.WORKOUT_ID
            GROUP BY
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL
            ORDER BY
                w.WORKOUT_DATE DESC,
                AO_DESCRIPTIONS ASC
            """
        )
        rows = db.execute(query, {"limit": page_size, "offset": offset}).mappings().all()
        return [cls._map_row_to_workout(row) for row in rows]

    @classmethod
    @timed_service
    def get_workouts_by_date(
        cls,
        db: Session,
        year: int,
        month: int | None = None,
        day: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[WorkoutResponse]:
        """Retrieve workouts filtered by year, year+month, or exact date using indexed derived table pagination."""
        offset = cls.get_offset(page, page_size)

        if month is None and day is None:
            # Year search: Jan 1 to Dec 31
            start_date = f"{year:04d}-01-01"
            end_date = f"{year:04d}-12-31"
        elif day is None:
            # Month search: 1st to last day of month
            _, last_day = calendar.monthrange(year, month)  # type: ignore[arg-type]
            start_date = f"{year:04d}-{month:02d}-01"
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        else:
            # Day search
            start_date = f"{year:04d}-{month:02d}-{day:02d}"
            end_date = start_date

        query = text(
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
                COUNT(DISTINCT wp.MEMBER_ID) AS PAX_COUNT
            FROM (
                SELECT WORKOUT_ID, WORKOUT_DATE, TITLE, AUTHOR, SLUG, BACKBLAST_URL
                FROM WORKOUT
                WHERE WORKOUT_DATE BETWEEN :start_date AND :end_date
                ORDER BY WORKOUT_DATE DESC, WORKOUT_ID DESC
                LIMIT :limit OFFSET :offset
            ) w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_PAX wp ON w.WORKOUT_ID = wp.WORKOUT_ID
            GROUP BY
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL
            ORDER BY
                w.WORKOUT_DATE DESC,
                AO_DESCRIPTIONS ASC
            """
        )
        rows = (
            db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            .mappings()
            .all()
        )
        return [cls._map_row_to_workout(row) for row in rows]

    @classmethod
    @timed_service
    def get_workouts_by_ao(
        cls,
        db: Session,
        ao_identifier: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[WorkoutResponse]:
        """Retrieve workouts filtered by AO ID or AO slug using indexed pagination."""
        offset = cls.get_offset(page, page_size)
        is_numeric = ao_identifier.isdigit()

        ao_filter = "ao_filter.AO_ID = :ao_val" if is_numeric else "ao_filter.SLUG = :ao_val"
        query = text(
            f"""
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
                COUNT(DISTINCT wp.MEMBER_ID) AS PAX_COUNT
            FROM (
                SELECT w_inner.WORKOUT_ID, w_inner.WORKOUT_DATE, w_inner.TITLE, w_inner.AUTHOR, w_inner.SLUG, w_inner.BACKBLAST_URL
                FROM WORKOUT w_inner
                INNER JOIN WORKOUT_AO wao_f ON w_inner.WORKOUT_ID = wao_f.WORKOUT_ID
                INNER JOIN AO ao_filter ON wao_f.AO_ID = ao_filter.AO_ID
                WHERE {ao_filter}
                ORDER BY w_inner.WORKOUT_DATE DESC, w_inner.WORKOUT_ID DESC
                LIMIT :limit OFFSET :offset
            ) w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_PAX wp ON w.WORKOUT_ID = wp.WORKOUT_ID
            GROUP BY
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL
            ORDER BY
                w.WORKOUT_DATE DESC,
                AO_DESCRIPTIONS ASC
            """
        )
        val = int(ao_identifier) if is_numeric else ao_identifier
        rows = (
            db.execute(query, {"ao_val": val, "limit": page_size, "offset": offset})
            .mappings()
            .all()
        )
        return [cls._map_row_to_workout(row) for row in rows]

    @classmethod
    @timed_service
    def get_workout_by_id(cls, db: Session, workout_id: int) -> WorkoutResponse | None:
        """Retrieve full details for a single workout including the PAX attendee list."""
        query = text(
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
                wd.HTML_CONTENT
            FROM
                WORKOUT w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_DETAILS wd ON w.WORKOUT_ID = wd.WORKOUT_ID
            WHERE
                w.WORKOUT_ID = :workout_id
            GROUP BY
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL,
                wd.HTML_CONTENT
            """
        )
        row = db.execute(query, {"workout_id": workout_id}).mappings().first()
        if not row:
            return None

        workout = cls._map_row_to_workout(row)

        # Retrieve full PAX attendee roster
        pax_query = text(
            """
            SELECT m.MEMBER_ID, m.F3_NAME
            FROM WORKOUT_PAX wp
            INNER JOIN MEMBER m ON wp.MEMBER_ID = m.MEMBER_ID
            WHERE wp.WORKOUT_ID = :workout_id
            ORDER BY m.F3_NAME ASC
            """
        )
        pax_rows = db.execute(pax_query, {"workout_id": workout_id}).mappings().all()
        workout.pax = [
            MemberSummary(memberId=p["MEMBER_ID"], f3Name=p["F3_NAME"]) for p in pax_rows
        ]
        workout.pax_count = len(workout.pax)
        workout.content = row.get("HTML_CONTENT")
        return workout

    @classmethod
    @timed_service
    def get_workout_by_date_and_slug(
        cls, db: Session, year: int, month: int, day: int, slug: str
    ) -> WorkoutResponse | None:
        """Retrieve a workout matching exact date and slug, with PAX roster."""
        workout_date = f"{year:04d}-{month:02d}-{day:02d}"
        query = text(
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
                wd.HTML_CONTENT
            FROM
                WORKOUT w
            LEFT OUTER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            LEFT OUTER JOIN AO ao ON wao.AO_ID = ao.AO_ID
            LEFT OUTER JOIN WORKOUT_Q wq ON w.WORKOUT_ID = wq.WORKOUT_ID
            LEFT OUTER JOIN MEMBER mq ON wq.MEMBER_ID = mq.MEMBER_ID
            LEFT OUTER JOIN WORKOUT_DETAILS wd ON w.WORKOUT_ID = wd.WORKOUT_ID
            WHERE
                w.WORKOUT_DATE = :workout_date AND w.SLUG = :slug
            GROUP BY
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                w.TITLE,
                w.AUTHOR,
                w.SLUG,
                w.BACKBLAST_URL,
                wd.HTML_CONTENT
            """
        )
        row = (
            db.execute(query, {"workout_date": workout_date, "slug": slug}).mappings().first()
        )
        if not row:
            return None

        workout_id = row["WORKOUT_ID"]
        workout = cls._map_row_to_workout(row)

        # Retrieve full PAX attendee roster
        pax_query = text(
            """
            SELECT m.MEMBER_ID, m.F3_NAME
            FROM WORKOUT_PAX wp
            INNER JOIN MEMBER m ON wp.MEMBER_ID = m.MEMBER_ID
            WHERE wp.WORKOUT_ID = :workout_id
            ORDER BY m.F3_NAME ASC
            """
        )
        pax_rows = db.execute(pax_query, {"workout_id": workout_id}).mappings().all()
        workout.pax = [
            MemberSummary(memberId=p["MEMBER_ID"], f3Name=p["F3_NAME"]) for p in pax_rows
        ]
        workout.pax_count = len(workout.pax)
        workout.content = row.get("HTML_CONTENT")
        return workout

    @staticmethod
    def _map_row_to_workout(row: dict) -> WorkoutResponse:
        """Map raw database row mapping to strongly-typed WorkoutResponse DTO."""
        # Parse AO associations
        ao_list: list[AOSummary] = []
        ao_ids_raw = row.get("AO_IDS")
        ao_descs_raw = row.get("AO") or row.get("AO_DESCRIPTIONS")
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

        # Parse Q associations
        q_list: list[MemberSummary] = []
        q_ids_raw = row.get("Q_IDS")
        q_names_raw = row.get("Q") or row.get("Q_NAMES")

        if q_names_raw:
            q_ids = [int(i.strip()) for i in str(q_ids_raw).split(",") if i.strip().isdigit()]
            q_names = [n.strip() for n in str(q_names_raw).split(",") if n.strip()]

            for idx, name in enumerate(q_names):
                q_id = q_ids[idx] if idx < len(q_ids) else 0
                q_list.append(MemberSummary(memberId=q_id, f3Name=name))

        workout_date_val = row["WORKOUT_DATE"]
        workout_date_str = (
            workout_date_val.strftime("%Y-%m-%d")
            if isinstance(workout_date_val, (datetime.date, datetime.datetime))
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
            content=row.get("HTML_CONTENT"),
        )
