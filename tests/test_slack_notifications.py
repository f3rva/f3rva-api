"""Unit and Integration Tests for Slack Notification Dispatch Service."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

from src.services.slack_notification_service import SlackNotificationService


def test_slack_notification_skipped_if_unconfigured() -> None:
    """Verify notification is skipped and returns False if bot token or channel ID is missing."""
    with patch("src.services.slack_notification_service.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = None
        mock_settings.return_value.slack_backblast_channel_id = None
        res = SlackNotificationService.post_backblast_summary(
            title="Test Beatdown",
            workout_date="2026-08-01",
            url="https://f3rva.org/post",
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Dingo", "Lab Rat"],
        )
        assert res is False


def test_slack_notification_success() -> None:
    """Verify Block Kit message is constructed and sent successfully via Slack API."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        pax_list = [f"PAX_{i}" for i in range(12)]
        res = SlackNotificationService.post_backblast_summary(
            title="Massive Beatdown",
            workout_date="2026-08-01",
            url="https://f3rva.org/massive-beatdown",
            author="Dingo",
            aos=["Dogpile", "Gridiron"],
            q_names=["Dingo", "Splinter"],
            pax_names=pax_list,
        )
        assert res is True
        assert mock_urlopen.called


def test_slack_notification_error_response_handled_gracefully() -> None:
    """Verify Slack API error responses return False without throwing exceptions."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": false, "error": "channel_not_found"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp):
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C_INVALID"

        res = SlackNotificationService.post_backblast_summary(
            title="Error Test",
            workout_date="2026-08-01",
            url=None,
            author=None,
            aos=[],
            q_names=[],
            pax_names=[],
        )
        assert res is False


def test_slack_notification_network_exception_handled_gracefully() -> None:
    """Verify network timeouts and URLErrors are caught gracefully and return False."""
    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.post_backblast_summary(
            title="Network Error Test",
            workout_date="2026-08-01",
            url=None,
            author="Dingo",
            aos=["Gridiron"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res is False
