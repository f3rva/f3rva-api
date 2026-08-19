"""Service layer for analytical reports, attendance leaderboards, AO metrics, and streaks."""

from __future__ import annotations

import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from src.models.schemas import (
    AOAttendanceSummary,
    AOLeaderboardResponse,
    AttendanceLeaderboardItem,
    DayOfWeekAttendance,
    LeaderboardEntry,
    MemberAODistribution,
    MemberDistributionResponse,
)
from src.utils.logging import timed_service

DAY_NAMES = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
    7: "Saturday",
}


class ReportService:
    """Analytical queries, leaderboard computations, and attendance aggregation."""

    @classmethod
    @timed_service
    def get_attendance_leaderboard(
        cls,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
        sort_by: str = "workout",
        min_qs: int = 0,
        min_workouts: int = 0,
        limit: int | None = None,
    ) -> list[AttendanceLeaderboardItem]:
        """Generate member attendance and Q leaderboard within an optional date range."""
        query = text(
            """
            SELECT
                m.MEMBER_ID,
                m.F3_NAME,
                COALESCE(pax_agg.WORKOUT_COUNT, 0) AS WORKOUT_COUNT,
                COALESCE(q_agg.Q_COUNT, 0) AS Q_COUNT
            FROM MEMBER m
            LEFT OUTER JOIN (
                SELECT wp.MEMBER_ID, COUNT(DISTINCT wp.WORKOUT_ID) AS WORKOUT_COUNT
                FROM WORKOUT_PAX wp
                INNER JOIN WORKOUT w ON wp.WORKOUT_ID = w.WORKOUT_ID
                WHERE (:start_date IS NULL OR w.WORKOUT_DATE >= :start_date)
                  AND (:end_date IS NULL OR w.WORKOUT_DATE <= :end_date)
                GROUP BY wp.MEMBER_ID
            ) pax_agg ON m.MEMBER_ID = pax_agg.MEMBER_ID
            LEFT OUTER JOIN (
                SELECT wq.MEMBER_ID, COUNT(DISTINCT wq.WORKOUT_ID) AS Q_COUNT
                FROM WORKOUT_Q wq
                INNER JOIN WORKOUT w ON wq.WORKOUT_ID = w.WORKOUT_ID
                WHERE (:start_date IS NULL OR w.WORKOUT_DATE >= :start_date)
                  AND (:end_date IS NULL OR w.WORKOUT_DATE <= :end_date)
                GROUP BY wq.MEMBER_ID
            ) q_agg ON m.MEMBER_ID = q_agg.MEMBER_ID
            WHERE (COALESCE(pax_agg.WORKOUT_COUNT, 0) > 0 OR COALESCE(q_agg.Q_COUNT, 0) > 0)
              AND m.MEMBER_ID != 123
            """
        )
        rows = (
            db.execute(query, {"start_date": start_date, "end_date": end_date})
            .mappings()
            .all()
        )

        items: list[AttendanceLeaderboardItem] = []
        for r in rows:
            w_count = int(r["WORKOUT_COUNT"])
            q_count = int(r["Q_COUNT"])
            ratio = round(q_count / w_count, 4) if w_count > 0 else 0.0

            if min_qs > 0 and q_count < min_qs:
                continue
            if min_workouts > 0 and w_count < min_workouts:
                continue

            items.append(
                AttendanceLeaderboardItem(
                    memberId=r["MEMBER_ID"],
                    f3Name=r["F3_NAME"],
                    numWorkouts=w_count,
                    numQs=q_count,
                    qRatio=ratio,
                )
            )

        # Sort according to sort_by parameter
        if sort_by == "q":
            items.sort(key=lambda x: (x.num_qs, x.num_workouts, x.f3_name), reverse=True)
        elif sort_by == "ratio":
            items.sort(key=lambda x: (x.q_ratio, x.num_qs, x.num_workouts, x.f3_name), reverse=True)
        else:  # default 'workout'
            items.sort(key=lambda x: (x.num_workouts, x.num_qs, x.f3_name), reverse=True)

        if limit is not None and limit > 0:
            return items[:limit]
        return items

    @classmethod
    @timed_service
    def get_ao_attendance_summary(
        cls,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[AOAttendanceSummary]:
        """Calculate total workouts, total PAX attendance, and average PAX per AO."""
        effective_start = start_date or "2014-01-01"
        effective_end = end_date or datetime.date.today().isoformat()

        query = text(
            """
            SELECT
                ao.AO_ID,
                ao.DESCRIPTION,
                ao.SLUG,
                COUNT(DISTINCT w.WORKOUT_ID) AS TOTAL_WORKOUTS,
                COUNT(wp.MEMBER_ID) AS TOTAL_PAX
            FROM AO ao
            INNER JOIN WORKOUT_AO wao ON ao.AO_ID = wao.AO_ID
            INNER JOIN WORKOUT w ON wao.WORKOUT_ID = w.WORKOUT_ID
            LEFT OUTER JOIN WORKOUT_PAX wp ON w.WORKOUT_ID = wp.WORKOUT_ID AND wp.MEMBER_ID != 123
            WHERE w.WORKOUT_DATE >= :start_date
              AND w.WORKOUT_DATE <= :end_date
            GROUP BY ao.AO_ID, ao.DESCRIPTION, ao.SLUG
            ORDER BY ao.DESCRIPTION ASC
            """
        )
        rows = (
            db.execute(query, {"start_date": effective_start, "end_date": effective_end})
            .mappings()
            .all()
        )

        summaries: list[AOAttendanceSummary] = []
        for r in rows:
            total_w = int(r["TOTAL_WORKOUTS"])
            total_p = int(r["TOTAL_PAX"])
            avg_p = round(total_p / total_w, 2) if total_w > 0 else 0.0
            summaries.append(
                AOAttendanceSummary(
                    aoId=r["AO_ID"],
                    description=r["DESCRIPTION"],
                    slug=r["SLUG"],
                    totalWorkouts=total_w,
                    totalPax=total_p,
                    averagePax=avg_p,
                )
            )

        summaries.sort(key=lambda x: x.average_pax, reverse=True)
        return summaries

    @classmethod
    @timed_service
    def get_ao_leaderboard(
        cls, db: Session, ao_id: int, limit: int = 10
    ) -> AOLeaderboardResponse | None:
        """Retrieve top leaders (Qs), top attendees, and active streaks for an AO."""
        ao_row = db.execute(
            text("SELECT AO_ID, DESCRIPTION FROM AO WHERE AO_ID = :ao_id"),
            {"ao_id": ao_id},
        ).mappings().first()
        if not ao_row:
            return None

        # 1. Top Qs at AO
        top_qs_query = text(
            """
            SELECT m.MEMBER_ID, m.F3_NAME, COUNT(DISTINCT w.WORKOUT_ID) AS Q_COUNT
            FROM WORKOUT_Q wq
            INNER JOIN MEMBER m ON wq.MEMBER_ID = m.MEMBER_ID
            INNER JOIN WORKOUT w ON wq.WORKOUT_ID = w.WORKOUT_ID
            INNER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            WHERE wao.AO_ID = :ao_id
              AND m.MEMBER_ID != 123
            GROUP BY m.MEMBER_ID, m.F3_NAME
            ORDER BY Q_COUNT DESC, m.F3_NAME ASC
            LIMIT :limit
            """
        )
        top_qs_rows = (
            db.execute(top_qs_query, {"ao_id": ao_id, "limit": limit}).mappings().all()
        )
        top_qs = [
            LeaderboardEntry(id=r["MEMBER_ID"], name=r["F3_NAME"], count=r["Q_COUNT"])
            for r in top_qs_rows
        ]

        # 2. Top PAX at AO
        top_pax_query = text(
            """
            SELECT m.MEMBER_ID, m.F3_NAME, COUNT(DISTINCT w.WORKOUT_ID) AS PAX_COUNT
            FROM WORKOUT_PAX wp
            INNER JOIN MEMBER m ON wp.MEMBER_ID = m.MEMBER_ID
            INNER JOIN WORKOUT w ON wp.WORKOUT_ID = w.WORKOUT_ID
            INNER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            WHERE wao.AO_ID = :ao_id
              AND m.MEMBER_ID != 123
            GROUP BY m.MEMBER_ID, m.F3_NAME
            ORDER BY PAX_COUNT DESC, m.F3_NAME ASC
            LIMIT :limit
            """
        )
        top_pax_rows = (
            db.execute(top_pax_query, {"ao_id": ao_id, "limit": limit}).mappings().all()
        )
        top_pax = [
            LeaderboardEntry(id=r["MEMBER_ID"], name=r["F3_NAME"], count=r["PAX_COUNT"])
            for r in top_pax_rows
        ]

        # 3. Calculate Streakers (Consecutive workout attendance at AO)
        streakers = cls._calculate_ao_streakers(db=db, ao_id=ao_id, limit=limit)

        return AOLeaderboardResponse(
            aoId=ao_row["AO_ID"],
            description=ao_row["DESCRIPTION"],
            topQs=top_qs,
            topPax=top_pax,
            streakers=streakers,
        )

    @classmethod
    @timed_service
    def get_day_of_week_attendance(
        cls,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[DayOfWeekAttendance]:
        """Aggregate total workouts and PAX attendance by day of the week (1=Sunday..7=Saturday)."""
        effective_start = start_date or "2014-01-01"
        effective_end = end_date or datetime.date.today().isoformat()

        query = text(
            """
            SELECT
                w.WORKOUT_ID,
                w.WORKOUT_DATE,
                COUNT(wp.MEMBER_ID) AS PAX_COUNT
            FROM WORKOUT w
            LEFT OUTER JOIN WORKOUT_PAX wp ON w.WORKOUT_ID = wp.WORKOUT_ID AND wp.MEMBER_ID != 123
            WHERE w.WORKOUT_DATE >= :start_date
              AND w.WORKOUT_DATE <= :end_date
            GROUP BY w.WORKOUT_ID, w.WORKOUT_DATE
            """
        )
        rows = (
            db.execute(query, {"start_date": effective_start, "end_date": effective_end})
            .mappings()
            .all()
        )

        day_stats: dict[int, dict[str, int]] = {
            i: {"workouts": 0, "pax": 0} for i in range(1, 8)
        }

        for r in rows:
            date_val = r["WORKOUT_DATE"]
            if isinstance(date_val, str):
                parsed_date = datetime.date.fromisoformat(date_val)
            elif isinstance(date_val, datetime.datetime):
                parsed_date = date_val.date()
            else:
                parsed_date = date_val

            # Python weekday: 0=Mon..6=Sun -> Convert to SQL standard 1=Sun..7=Sat
            day_id = (parsed_date.weekday() + 1) % 7 + 1
            day_stats[day_id]["workouts"] += 1
            day_stats[day_id]["pax"] += int(r["PAX_COUNT"] or 0)

        results: list[DayOfWeekAttendance] = []
        for day_id in range(1, 8):
            w_count = day_stats[day_id]["workouts"]
            p_count = day_stats[day_id]["pax"]
            avg = round(p_count / w_count, 2) if w_count > 0 else 0.0
            results.append(
                DayOfWeekAttendance(
                    dayId=day_id,
                    dayName=DAY_NAMES[day_id],
                    workoutCount=w_count,
                    totalPax=p_count,
                    averagePax=avg,
                )
            )

        return results

    @classmethod
    @timed_service
    def get_member_distribution(
        cls, db: Session, member_id: int
    ) -> MemberDistributionResponse | None:
        """Retrieve breakdown of workouts attended and Q'd across all AOs for a member."""
        if member_id == 123:
            return None

        member_row = db.execute(
            text("SELECT MEMBER_ID, F3_NAME FROM MEMBER WHERE MEMBER_ID = :member_id"),
            {"member_id": member_id},
        ).mappings().first()
        if not member_row:
            return None

        query = text(
            """
            SELECT
                ao.AO_ID,
                ao.DESCRIPTION,
                COALESCE(q_agg.Q_COUNT, 0) AS Q_COUNT,
                COALESCE(pax_agg.PAX_COUNT, 0) AS PAX_COUNT
            FROM AO ao
            LEFT OUTER JOIN (
                SELECT wao.AO_ID, COUNT(DISTINCT wq.WORKOUT_ID) AS Q_COUNT
                FROM WORKOUT_Q wq
                INNER JOIN WORKOUT_AO wao ON wq.WORKOUT_ID = wao.WORKOUT_ID
                WHERE wq.MEMBER_ID = :member_id
                GROUP BY wao.AO_ID
            ) q_agg ON ao.AO_ID = q_agg.AO_ID
            LEFT OUTER JOIN (
                SELECT wao.AO_ID, COUNT(DISTINCT wp.WORKOUT_ID) AS PAX_COUNT
                FROM WORKOUT_PAX wp
                INNER JOIN WORKOUT_AO wao ON wp.WORKOUT_ID = wao.WORKOUT_ID
                WHERE wp.MEMBER_ID = :member_id
                GROUP BY wao.AO_ID
            ) pax_agg ON ao.AO_ID = pax_agg.AO_ID
            WHERE COALESCE(q_agg.Q_COUNT, 0) > 0 OR COALESCE(pax_agg.PAX_COUNT, 0) > 0
            ORDER BY PAX_COUNT DESC, Q_COUNT DESC, ao.DESCRIPTION ASC
            """
        )
        rows = db.execute(query, {"member_id": member_id}).mappings().all()
        distribution = [
            MemberAODistribution(
                aoId=r["AO_ID"],
                description=r["DESCRIPTION"],
                qCount=int(r["Q_COUNT"]),
                paxCount=int(r["PAX_COUNT"]),
            )
            for r in rows
        ]

        return MemberDistributionResponse(
            memberId=member_row["MEMBER_ID"],
            f3Name=member_row["F3_NAME"],
            distribution=distribution,
        )

    @classmethod
    def _calculate_ao_streakers(
        cls, db: Session, ao_id: int, limit: int = 10
    ) -> list[LeaderboardEntry]:
        """Calculate consecutive workout attendance streaks for an AO starting from the most recent workout."""
        # 1. Fetch recent workouts at this AO ordered newest to oldest
        workouts_query = text(
            """
            SELECT w.WORKOUT_ID, w.WORKOUT_DATE
            FROM WORKOUT w
            INNER JOIN WORKOUT_AO wao ON w.WORKOUT_ID = wao.WORKOUT_ID
            WHERE wao.AO_ID = :ao_id
            ORDER BY w.WORKOUT_DATE DESC, w.WORKOUT_ID DESC
            LIMIT 52
            """
        )
        workout_rows = db.execute(workouts_query, {"ao_id": ao_id}).mappings().all()
        if not workout_rows:
            return []

        workout_ids = [r["WORKOUT_ID"] for r in workout_rows]

        # 2. Fetch all attendee records for these workouts
        pax_query = text(
            """
            SELECT wp.WORKOUT_ID, m.MEMBER_ID, m.F3_NAME
            FROM WORKOUT_PAX wp
            INNER JOIN MEMBER m ON wp.MEMBER_ID = m.MEMBER_ID
            WHERE wp.WORKOUT_ID IN :workout_ids
              AND m.MEMBER_ID != 123
            """
        ).bindparams(bindparam("workout_ids", expanding=True))
        pax_rows = (
            db.execute(pax_query, {"workout_ids": list(workout_ids)}).mappings().all()
        )

        # Build map: workout_id -> set of member_ids and member_id -> name
        workout_attendees: dict[int, set[int]] = {wid: set() for wid in workout_ids}
        member_names: dict[int, str] = {}
        for p in pax_rows:
            workout_attendees[p["WORKOUT_ID"]].add(p["MEMBER_ID"])
            member_names[p["MEMBER_ID"]] = p["F3_NAME"]

        most_recent_workout_id = workout_ids[0]
        active_attendees = workout_attendees.get(most_recent_workout_id, set())

        streaks: list[LeaderboardEntry] = []
        for mid in active_attendees:
            streak_len = 0
            for wid in workout_ids:
                if mid in workout_attendees[wid]:
                    streak_len += 1
                else:
                    break  # Streak broken
            streaks.append(
                LeaderboardEntry(
                    id=mid,
                    name=member_names.get(mid, f"Member {mid}"),
                    count=streak_len,
                )
            )

        streaks.sort(key=lambda s: (s.count, s.name), reverse=True)
        return streaks[:limit]
