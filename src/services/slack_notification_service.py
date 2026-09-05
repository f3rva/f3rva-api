"""Service for dispatching Block Kit backblast summaries to Slack channels."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.config.settings import get_settings
from src.utils.logging import timed_service

logger = logging.getLogger(__name__)


def _escape_mrkdwn(text: str | None) -> str:
    """Escape Slack mrkdwn control characters (&, <, >) to prevent injection."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_safe_url(url: Any) -> bool:
    """Validate that a URL uses safe HTTP/HTTPS schemes and contains no mrkdwn control characters."""
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if any(c in url for c in ("<", ">", "|", " ", "\n", "\r", "\t")):
        return False
    return True


class SlackNotificationService:
    """Dispatches backblast notification cards to Slack channels via Bot Token."""

    @classmethod
    @timed_service
    def post_backblast_summary(
        cls,
        title: str,
        workout_date: str,
        url: str | None,
        author: str | None,
        aos: list[str],
        q_names: list[str],
        pax_names: list[str],
    ) -> bool:
        """Post a structured Block Kit message summarizing a published workout backblast."""
        settings = get_settings()
        if not settings.slack_bot_token or not settings.slack_backblast_channel_id:
            logger.info("Slack notifications not configured; skipping channel post.")
            return False

        # Escape untrusted user input against mrkdwn and mention injection
        escaped_title = _escape_mrkdwn(title)
        escaped_date = _escape_mrkdwn(workout_date)
        escaped_author = _escape_mrkdwn(author) if author else "PAX"
        escaped_aos = [_escape_mrkdwn(ao) for ao in aos]
        escaped_qs = [_escape_mrkdwn(q) for q in q_names]
        escaped_pax = [_escape_mrkdwn(p) for p in pax_names]

        # Format location and attendees
        ao_str = ", ".join(escaped_aos) if escaped_aos else "Unspecified AO"
        q_str = ", ".join(escaped_qs) if escaped_qs else "None recorded"
        pax_count = len(escaped_pax)
        pax_preview = ", ".join(escaped_pax[:8]) + (f" (+{pax_count - 8} more)" if pax_count > 8 else "")

        # Validate URL scheme to prevent link hijacking or malformed <None|...> headers
        raw_prefix = settings.backblast_url_prefix
        prefix = raw_prefix.rstrip("/") if isinstance(raw_prefix, str) and raw_prefix else None
        candidate_url = url or prefix
        post_link = candidate_url if _is_safe_url(candidate_url) else None

        header_text = f"<{post_link}|*{escaped_title}*>" if post_link else f"*{escaped_title}*"
        footer_text = f"Posted by *{escaped_author}*"

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Date:* {escaped_date}"},
                    {"type": "mrkdwn", "text": f"*AO:* {ao_str}"},
                    {"type": "mrkdwn", "text": f"*QIC:*\n{q_str}"},
                    {"type": "mrkdwn", "text": f"*PAX ({pax_count}):*\n{pax_preview}"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": footer_text},
                ],
            },
        ]

        payload = {
            "channel": settings.slack_backblast_channel_id,
            "text": f"{escaped_title} ({escaped_date}) at {ao_str}",
            "blocks": blocks,
        }

        data_encoded = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url="https://slack.com/api/chat.postMessage",
            data=data_encoded,
            headers={
                "Authorization": f"Bearer {settings.slack_bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                res_data = json.loads(body)
                if not res_data.get("ok"):
                    logger.warning("Failed to post to Slack: %s", res_data.get("error"))
                    return False
                return True
        except urllib.error.HTTPError as http_err:
            error_body = ""
            try:
                error_body = http_err.read().decode("utf-8", errors="replace")[:256]
            except Exception:
                pass
            logger.warning("HTTP error dispatching Slack notification: %s - %s", http_err, error_body)
            return False
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            logger.warning("Network error dispatching Slack notification: %s", err)
            return False
        except Exception as err:
            logger.error("Unexpected error dispatching Slack notification: %s", err)
            return False
