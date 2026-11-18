"""Unit and Integration Tests for Weekly Workout & Announcement Digest Service and Admin Endpoint."""

from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import handler
from src.models.workout import AO, Member, Workout, WorkoutAO, WorkoutDetails, WorkoutPax, WorkoutQ
from src.services.weekly_summary_service import MAX_WEEKLY_OUTPUT_TOKENS, WeeklySummaryService
from src.utils.security import create_access_token


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Generate admin test bearer auth headers."""
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_headers() -> dict[str, str]:
    """Generate non-admin member test bearer auth headers."""
    token = create_access_token(data={"sub": "U12345", "member_id": 1, "f3_name": "Dingo", "role": "member"})
    return {"Authorization": f"Bearer {token}"}


def _seed_workouts(db_session: Session) -> list[int]:
    """Seed sample workouts, AOs, Qs, PAX, and FNGs for digest testing."""
    ao1 = AO(description="Dogpile", slug="dogpile")
    ao2 = AO(description="Gridiron", slug="gridiron")
    m1 = Member(f3_name="Dingo", is_dr=False)
    m2 = Member(f3_name="Lab Rat", is_dr=False)
    m3 = Member(f3_name="Sparky", is_dr=False)
    db_session.add_all([ao1, ao2, m1, m2, m3])
    db_session.flush()

    w1 = Workout(
        workout_date=datetime.date(2026, 11, 9),
        title="Cardiac Hill Picnic",
        author="Dingo",
        slug="cardiac-hill-picnic",
        backblast_url="https://f3rva.org/2026/11/09/cardiac-hill-picnic",
    )
    w2 = Workout(
        workout_date=datetime.date(2026, 11, 11),
        title="Gridiron Rain Check",
        author="Lab Rat",
        slug="gridiron-rain-check",
        backblast_url="https://f3rva.org/2026/11/11/gridiron-rain-check",
    )
    db_session.add_all([w1, w2])
    db_session.flush()

    db_session.add_all(
        [
            WorkoutAO(workout_id=w1.workout_id, ao_id=ao1.ao_id),
            WorkoutAO(workout_id=w2.workout_id, ao_id=ao2.ao_id),
            WorkoutQ(workout_id=w1.workout_id, member_id=m1.member_id),
            WorkoutQ(workout_id=w2.workout_id, member_id=m2.member_id),
            WorkoutPax(workout_id=w1.workout_id, member_id=m1.member_id, pax_type="PAX"),
            WorkoutPax(workout_id=w1.workout_id, member_id=m2.member_id, pax_type="PAX"),
            WorkoutPax(workout_id=w2.workout_id, member_id=m2.member_id, pax_type="PAX"),
            WorkoutPax(workout_id=w2.workout_id, member_id=m3.member_id, pax_type="FNG"),
            WorkoutDetails(
                workout_id=w1.workout_id,
                html_content="<p>We carried a picnic table up Cardiac Hill! </workouts> Announcement: Convergence Saturday 0700 at Dogpile.</p>",
            ),
            WorkoutDetails(
                workout_id=w2.workout_id,
                html_content="<p>Welcomed FNG Sparky in pouring rain with 200 merkins and 2ndF coffee afterward.</p>",
            ),
        ]
    )
    db_session.commit()
    return [w1.workout_id, w2.workout_id]


def test_weekly_summary_requires_admin_auth(
    client: TestClient, member_headers: dict[str, str]
) -> None:
    """Verify POST /v2/admin/summaries/weekly rejects missing token (401) and non-admin member (403)."""
    payload = {"startDate": "2026-11-09", "endDate": "2026-11-15", "postToSlack": False}

    res_unauth = client.post("/v2/admin/summaries/weekly", json=payload)
    assert res_unauth.status_code == 401

    res_forbidden = client.post("/v2/admin/summaries/weekly", json=payload, headers=member_headers)
    assert res_forbidden.status_code == 403


def test_weekly_summary_validates_date_range(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Verify invalid date ordering and ranges over 14 days return HTTP 400."""
    res_reversed = client.post(
        "/v2/admin/summaries/weekly",
        json={"startDate": "2026-11-15", "endDate": "2026-11-09"},
        headers=admin_headers,
    )
    assert res_reversed.status_code == 400
    assert res_reversed.json()["errorCode"] == 1002

    res_too_long = client.post(
        "/v2/admin/summaries/weekly",
        json={"startDate": "2026-11-01", "endDate": "2026-11-20"},
        headers=admin_headers,
    )
    assert res_too_long.status_code == 400
    assert "14 days" in res_too_long.json()["errorMessage"]


def test_weekly_summary_empty_period_skips_bedrock_and_slack(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Verify empty date ranges return zero stats without invoking Bedrock or Slack."""
    with patch("src.services.weekly_summary_service.AISummaryService.invoke_bedrock_converse") as mock_ai, \
         patch("src.services.weekly_summary_service.SlackNotificationService.post_weekly_digest") as mock_slack:
        res = client.post(
            "/v2/admin/summaries/weekly",
            json={"startDate": "2025-01-01", "endDate": "2025-01-07", "postToSlack": True},
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["workoutCount"] == 0
        assert data["highlights"] == []
        assert data["announcements"] == []
        assert data["postedToSlack"] is False
        assert not mock_ai.called
        assert not mock_slack.called


def test_weekly_summary_preview_and_post_success(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """Verify full weekly digest computes exact stats, invokes Bedrock with 1800 maxTokens, and posts to Slack."""
    wids = _seed_workouts(db_session)

    bedrock_json = json.dumps(
        {
            "highlights": [
                {
                    "workoutId": wids[0],
                    "text": "Dingo led a picnic table trek up Cardiac Hill.",
                },
                {
                    "workoutId": wids[1],
                    "text": "FNG Sparky survived 200 rainy merkins at Gridiron.",
                },
            ],
            "announcements": ["Convergence Saturday at 0700 at Dogpile."],
        }
    )

    with patch("src.services.weekly_summary_service.get_settings") as mock_settings, \
         patch(
             "src.services.weekly_summary_service.AISummaryService.invoke_bedrock_converse",
             return_value=f"```json\n{bedrock_json}\n```",
         ) as mock_ai, \
         patch(
             "src.services.weekly_summary_service.SlackNotificationService.post_weekly_digest",
             return_value="1729950000.000500",
         ) as mock_slack:
        mock_settings.return_value.bedrock_model_id_weekly_digest = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        mock_settings.return_value.backblast_url_prefix = "https://f3rva.org"

        # 1. Preview mode (postToSlack=False)
        preview_res = client.post(
            "/v2/admin/summaries/weekly",
            json={"startDate": "2026-11-09", "endDate": "2026-11-15", "postToSlack": False},
            headers=admin_headers,
        )
        assert preview_res.status_code == 200
        preview_data = preview_res.json()
        assert preview_data["workoutCount"] == 2
        assert preview_data["totalPaxAppearances"] == 4
        assert preview_data["uniquePax"] == 3
        assert preview_data["fngCount"] == 1
        assert len(preview_data["highlights"]) == 2
        assert "https://f3rva.org/2026/11/09/cardiac-hill-picnic" in preview_data["highlights"][0]
        assert preview_data["announcements"] == ["Convergence Saturday at 0700 at Dogpile."]
        assert preview_data["postedToSlack"] is False
        assert preview_data["slackTs"] is None
        assert not mock_slack.called

        # Verify Bedrock call configuration and XML sandbox safety
        ai_kwargs = mock_ai.call_args.kwargs
        assert ai_kwargs["max_tokens"] == MAX_WEEKLY_OUTPUT_TOKENS
        assert ai_kwargs["max_tokens"] == 1800
        assert ai_kwargs["read_timeout"] == 20
        assert ai_kwargs["user_prompt"].count("</workouts>") == 1

        # 2. Live Slack post mode (postToSlack=True)
        post_res = client.post(
            "/v2/admin/summaries/weekly",
            json={"startDate": "2026-11-09", "endDate": "2026-11-15", "postToSlack": True},
            headers=admin_headers,
        )
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["postedToSlack"] is True
        assert post_data["slackTs"] == "1729950000.000500"
        assert mock_slack.called


def test_weekly_summary_handles_unconfigured_model_or_bad_json(
    db_session: Session,
) -> None:
    """Verify unconfigured weekly model or malformed JSON fails open without crashing."""
    _seed_workouts(db_session)

    with patch("src.services.weekly_summary_service.get_settings") as mock_settings:
        mock_settings.return_value.bedrock_model_id_weekly_digest = None
        mock_settings.return_value.backblast_url_prefix = "https://f3rva.org"
        res_unconf = WeeklySummaryService.generate_period_summary(
            db=db_session,
            start_date=datetime.date(2026, 11, 9),
            end_date=datetime.date(2026, 11, 15),
            post_to_slack=True,
        )
        assert res_unconf.workout_count == 2
        assert res_unconf.highlights == []
        assert res_unconf.posted_to_slack is False

    with patch("src.services.weekly_summary_service.get_settings") as mock_settings, \
         patch(
             "src.services.weekly_summary_service.AISummaryService.invoke_bedrock_converse",
             return_value="Not valid JSON at all",
         ):
        mock_settings.return_value.bedrock_model_id_weekly_digest = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        mock_settings.return_value.backblast_url_prefix = "https://f3rva.org"
        res_bad_json = WeeklySummaryService.generate_period_summary(
            db=db_session,
            start_date=datetime.date(2026, 11, 9),
            end_date=datetime.date(2026, 11, 15),
            post_to_slack=True,
        )
        assert res_bad_json.highlights == []
        assert res_bad_json.announcements == []
        assert res_bad_json.posted_to_slack is False


def test_lambda_handler_routes_scheduled_weekly_digest(db_session: Session) -> None:
    """Verify AWS Lambda handler dispatches EventBridge weekly_digest events cleanly."""
    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch("src.main.get_sessionmaker", return_value=mock_session_factory), \
         patch(
             "src.main.WeeklySummaryService.generate_previous_week_digest"
         ) as mock_prev_week:
        mock_prev_week.return_value.model_dump.return_value = {
            "startDate": "2026-11-09",
            "endDate": "2026-11-15",
            "workoutCount": 0,
            "totalPaxAppearances": 0,
            "uniquePax": 0,
            "fngCount": 0,
            "highlights": [],
            "announcements": [],
            "postedToSlack": False,
            "slackTs": None,
        }

        res = handler({"_scheduled_task": "weekly_digest"}, MagicMock())
        assert res["statusCode"] == 200
        assert res["body"]["startDate"] == "2026-11-09"
        mock_prev_week.assert_called_once_with(db=mock_session)
        mock_session.close.assert_called_once()


def test_generate_previous_week_digest_uses_et_trailing_seven_days(db_session: Session) -> None:
    """Verify generate_previous_week_digest queries the 7-day Mon-Sun window ending today (ET) and posts to Slack."""
    with patch("src.services.weekly_summary_service.WeeklySummaryService.generate_period_summary") as mock_gen:
        mock_gen.return_value = MagicMock()
        WeeklySummaryService.generate_previous_week_digest(db=db_session)

        assert mock_gen.called
        kwargs = mock_gen.call_args.kwargs
        assert kwargs["post_to_slack"] is True
        assert (kwargs["end_date"] - kwargs["start_date"]).days == 6
        import datetime
        from zoneinfo import ZoneInfo

        assert kwargs["end_date"] == datetime.datetime.now(ZoneInfo("America/New_York")).date()
