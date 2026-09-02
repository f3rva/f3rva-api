"""Service for dispatching Block Kit backblast summaries to Slack channels."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from src.config.settings import get_settings
from src.utils.logging import timed_service

logger = logging.getLogger(__name__)


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

        # Format location and attendees
        ao_str = ", ".join(aos) if aos else "Unspecified AO"
        q_str = ", ".join(q_names) if q_names else "None recorded"
        pax_count = len(pax_names)
        pax_preview = ", ".join(pax_names[:8]) + (f" (+{pax_count - 8} more)" if pax_count > 8 else "")
        prefix = settings.backblast_url_prefix.rstrip("/") if settings.backblast_url_prefix else None
        post_link = url or prefix

        header_text = f"<{post_link}|*{title}*>"
        footer_text = f"Posted by *{author or 'PAX'}*"

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
                    {"type": "mrkdwn", "text": f"*Date:* {workout_date}"},
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
            "text": f"{title} ({workout_date}) at {ao_str}",
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
        except Exception as err:
            logger.warning("Network error dispatching Slack notification: %s", err)
            return False
