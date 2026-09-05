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


def test_slack_notification_escapes_mrkdwn_and_mentions() -> None:
    """Verify Slack control characters and broadcast mentions are sanitized."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"
        mock_settings.return_value.backblast_url_prefix = "https://f3rva.org"

        res = SlackNotificationService.post_backblast_summary(
            title="Beatdown <!channel> & <https://evil.com|Click Here>",
            workout_date="2026-08-01",
            url="https://f3rva.org/post/1",
            author="<@U12345> & Dingo",
            aos=["A & B <AO>"],
            q_names=["<QIC>"],
            pax_names=["<PAX_1>", "Tom & Jerry"],
        )
        assert res is True
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        # Verify broadcast mentions and angle brackets are escaped
        blocks = payload["blocks"]
        header_mrkdwn = blocks[0]["text"]["text"]
        assert "<!channel>" not in header_mrkdwn
        assert "&lt;!channel&gt;" in header_mrkdwn
        assert "&amp;" in header_mrkdwn

        fields = blocks[1]["fields"]
        assert "&lt;AO&gt;" in fields[1]["text"]
        assert "&lt;QIC&gt;" in fields[2]["text"]
        assert "&lt;PAX_1&gt;" in fields[3]["text"]

        footer = blocks[2]["elements"][0]["text"]
        assert "&lt;@U12345&gt;" in footer


def test_slack_notification_missing_url_renders_plain_header() -> None:
    """Verify missing URL does not render malformed <None|*Title*> header."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"
        mock_settings.return_value.backblast_url_prefix = None

        res = SlackNotificationService.post_backblast_summary(
            title="No URL Beatdown",
            workout_date="2026-08-01",
            url=None,
            author="Dingo",
            aos=["Dogpile"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res is True
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        header_mrkdwn = payload["blocks"][0]["text"]["text"]
        assert "<None|" not in header_mrkdwn
        assert header_mrkdwn == "*No URL Beatdown*"


def test_slack_notification_rejects_unsafe_urls() -> None:
    """Verify unsafe schemes (javascript:, ftp:) or URLs with delimiters are rejected."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"
        mock_settings.return_value.backblast_url_prefix = None

        res = SlackNotificationService.post_backblast_summary(
            title="Unsafe Link",
            workout_date="2026-08-01",
            url="javascript:alert('xss')",
            author="Attila",
            aos=["Dogpile"],
            q_names=["Attila"],
            pax_names=["Attila"],
        )
        assert res is True
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        header_mrkdwn = payload["blocks"][0]["text"]["text"]
        assert "javascript:" not in header_mrkdwn
        assert header_mrkdwn == "*Unsafe Link*"


def test_slack_notification_http_error_handled_gracefully() -> None:
    """Verify urllib.error.HTTPError logs bounded body and returns False."""
    from io import BytesIO

    http_error = urllib.error.HTTPError(
        url="https://slack.com/api/chat.postMessage",
        code=400,
        msg="Bad Request",
        hdrs={},  # type: ignore[arg-type]
        fp=BytesIO(b'{"ok": false, "error": "invalid_blocks"}'),
    )

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", side_effect=http_error):
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.post_backblast_summary(
            title="HTTP Error Test",
            workout_date="2026-08-01",
            url="https://f3rva.org/post/1",
            author="Dingo",
            aos=["Gridiron"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res is False
