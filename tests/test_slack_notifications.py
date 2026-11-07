"""Unit and Integration Tests for Slack Notification Dispatch Service."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

from src.services.slack_notification_service import SlackNotificationService


def test_slack_notification_skipped_if_unconfigured() -> None:
    """Verify notification is skipped and returns None if bot token or channel ID is missing."""
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
        assert res is None


def test_slack_notification_success() -> None:
    """Verify Block Kit message is constructed and sent successfully via Slack API, returning message ts."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
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
        assert res == "1729946793.000200"
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        pax_field_text = payload["blocks"][1]["fields"][3]["text"]
        assert "*PAX (12):*" in pax_field_text
        for pax_name in pax_list:
            assert pax_name in pax_field_text
        assert "more)" not in pax_field_text


def test_slack_notification_extracts_ts_from_nested_message() -> None:
    """Verify ts is extracted when nested inside 'message' object in Slack response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "message": {"ts": "1729946800.111222"}}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp):
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.post_backblast_summary(
            title="Nested TS Test",
            workout_date="2026-08-01",
            url="https://f3rva.org/nested-ts",
            author="Dingo",
            aos=["Dogpile"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res == "1729946800.111222"


def test_slack_notification_error_response_handled_gracefully() -> None:
    """Verify Slack API error responses return None without throwing exceptions."""
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
        assert res is None


def test_slack_notification_network_exception_handled_gracefully() -> None:
    """Verify network timeouts and URLErrors are caught gracefully and return None."""
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
        assert res is None


def test_slack_notification_escapes_mrkdwn_and_mentions() -> None:
    """Verify Slack control characters and broadcast mentions are sanitized."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
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
        assert res == "1729946793.000200"
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
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
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
        assert res == "1729946793.000200"
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        header_mrkdwn = payload["blocks"][0]["text"]["text"]
        assert "<None|" not in header_mrkdwn
        assert header_mrkdwn == "*No URL Beatdown*"


def test_slack_notification_rejects_unsafe_urls() -> None:
    """Verify unsafe schemes (javascript:, ftp:) or URLs with delimiters are rejected."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
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
        assert res == "1729946793.000200"
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        header_mrkdwn = payload["blocks"][0]["text"]["text"]
        assert "javascript:" not in header_mrkdwn
        assert header_mrkdwn == "*Unsafe Link*"


def test_slack_notification_http_error_handled_gracefully() -> None:
    """Verify urllib.error.HTTPError logs bounded body and returns None."""
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
        assert res is None


def test_slack_notification_with_fngs_and_drs() -> None:
    """Verify Slack notification conditionally includes FNGs and Downrange PAX when present."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.post_backblast_summary(
            title="Beatdown with FNG and DR",
            workout_date="2026-08-11",
            url="https://f3rva.org/beatdown",
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Lab Rat"],
            fng_names=["Sparky"],
            dr_names=["Outlaw (F3 Raleigh)"],
        )
        assert res == "1729946793.000200"
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        fields = payload["blocks"][1]["fields"]
        field_texts = [f["text"] for f in fields]

        assert any("*FNGs (1):*" in t and "Sparky" in t for t in field_texts)
        assert any("*Downrange (1):*" in t and "Outlaw" in t for t in field_texts)


def test_slack_notification_without_fngs_and_drs_omits_fields() -> None:
    """Verify Slack notification keeps message short and omits FNG and Downrange when empty."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.post_backblast_summary(
            title="Regular Beatdown",
            workout_date="2026-08-11",
            url="https://f3rva.org/beatdown",
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Lab Rat"],
            fng_names=[],
            dr_names=None,
        )
        assert res == "1729946793.000200"
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        fields = payload["blocks"][1]["fields"]
        field_texts = [f["text"] for f in fields]

        assert not any("*FNGs" in t for t in field_texts)
        assert not any("*Downrange" in t for t in field_texts)


def test_update_backblast_summary_success() -> None:
    """Verify chat.update is invoked with the message ts and updated PAX fields."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res = SlackNotificationService.update_backblast_summary(
            slack_ts="1729946793.000200",
            title="Updated Beatdown Title",
            workout_date="2026-08-11",
            url="https://f3rva.org/updated-beatdown",
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Lab Rat", "Splinter", "Swag"],
            fng_names=["NewGuy"],
            dr_names=["Outlaw"],
        )
        assert res is True
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://slack.com/api/chat.update"
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["channel"] == "C12345"
        assert payload["ts"] == "1729946793.000200"

        fields = payload["blocks"][1]["fields"]
        field_texts = [f["text"] for f in fields]
        assert any("*PAX (3):*" in t and "Lab Rat, Splinter, Swag" in t for t in field_texts)
        assert any("*FNGs (1):*" in t and "NewGuy" in t for t in field_texts)
        assert any("*Downrange (1):*" in t and "Outlaw" in t for t in field_texts)


def test_update_backblast_summary_skipped_when_unconfigured_or_missing_ts() -> None:
    """Verify update_backblast_summary returns False if unconfigured or slack_ts is empty."""
    with patch("src.services.slack_notification_service.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"

        res_empty_ts = SlackNotificationService.update_backblast_summary(
            slack_ts="",
            title="Test",
            workout_date="2026-08-11",
            url=None,
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res_empty_ts is False

        mock_settings.return_value.slack_bot_token = None
        res_no_token = SlackNotificationService.update_backblast_summary(
            slack_ts="1729946793.000200",
            title="Test",
            workout_date="2026-08-11",
            url=None,
            author="Dingo",
            aos=["First Watch"],
            q_names=["Dingo"],
            pax_names=["Dingo"],
        )
        assert res_no_token is False


def test_slack_notification_includes_sanitized_tldr_summary_block() -> None:
    """Verify TL;DR summary block is inserted below header and escapes mrkdwn control characters."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true, "ts": "1729946793.000200"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_notification_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mock_settings.return_value.slack_bot_token = "xoxb-test-token"
        mock_settings.return_value.slack_backblast_channel_id = "C12345"
        mock_settings.return_value.backblast_url_prefix = "https://f3rva.org"

        res = SlackNotificationService.post_backblast_summary(
            title="Summary Beatdown",
            workout_date="2026-08-15",
            url="https://f3rva.org/summary-beatdown",
            author="Dingo",
            aos=["Dogpile"],
            q_names=["Dingo"],
            pax_names=["Dingo", "Lab Rat"],
            summary="10 PAX crushed hill repeats & merkins <!channel>.",
        )
        assert res == "1729946793.000200"
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        blocks = payload["blocks"]
        assert len(blocks) == 4
        assert blocks[1]["type"] == "section"
        assert blocks[1]["text"]["text"] == "> *TL;DR:* _10 PAX crushed hill repeats &amp; merkins &lt;!channel&gt;._"


