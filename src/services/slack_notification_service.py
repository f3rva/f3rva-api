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
    """Dispatches and updates backblast notification cards in Slack channels via Bot Token."""

    @classmethod
    def _build_backblast_message(
        cls,
        title: str,
        workout_date: str,
        url: str | None,
        author: str | None,
        aos: list[str],
        q_names: list[str],
        pax_names: list[str],
        fng_names: list[str] | None = None,
        dr_names: list[str] | None = None,
        backblast_url_prefix: str | None = None,
        summary: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build sanitized fallback text and Block Kit blocks for a workout summary."""
        # Escape untrusted user input against mrkdwn and mention injection
        escaped_title = _escape_mrkdwn(title)
        escaped_date = _escape_mrkdwn(workout_date)
        escaped_author = _escape_mrkdwn(author) if author else "PAX"
        escaped_aos = [_escape_mrkdwn(ao) for ao in aos]
        escaped_qs = [_escape_mrkdwn(q) for q in q_names]
        escaped_pax = [_escape_mrkdwn(p) for p in pax_names]
        escaped_fngs = [_escape_mrkdwn(f) for f in (fng_names or [])]
        escaped_drs = [_escape_mrkdwn(d) for d in (dr_names or [])]
        escaped_summary = _escape_mrkdwn(summary.strip()) if summary and summary.strip() else None

        # Format location and attendees
        ao_str = ", ".join(escaped_aos) if escaped_aos else "Unspecified AO"
        q_str = ", ".join(escaped_qs) if escaped_qs else "None recorded"
        pax_count = len(escaped_pax)
        pax_str = ", ".join(escaped_pax)

        # Validate URL scheme to prevent link hijacking or malformed <None|...> headers
        prefix = (
            backblast_url_prefix.rstrip("/")
            if isinstance(backblast_url_prefix, str) and backblast_url_prefix
            else None
        )
        candidate_url = url or prefix
        post_link = candidate_url if _is_safe_url(candidate_url) else None

        header_text = f"<{post_link}|*{escaped_title}*>" if post_link else f"*{escaped_title}*"
        if escaped_summary:
            header_text = f"{header_text}\n_{escaped_summary}_"
        footer_text = f"Posted by *{escaped_author}*"

        fields = [
            {"type": "mrkdwn", "text": f"*Date:* {escaped_date}"},
            {"type": "mrkdwn", "text": f"*AO:* {ao_str}"},
            {"type": "mrkdwn", "text": f"*QIC:* {q_str}"},
            {"type": "mrkdwn", "text": f"*PAX ({pax_count}):* {pax_str}"},
        ]
        if escaped_fngs:
            fng_str = ", ".join(escaped_fngs)
            fields.append({"type": "mrkdwn", "text": f"*FNGs ({len(escaped_fngs)}):* {fng_str}"})
        if escaped_drs:
            dr_str = ", ".join(escaped_drs)
            fields.append(
                {"type": "mrkdwn", "text": f"*Downrange ({len(escaped_drs)}):* {dr_str}"}
            )

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
                "fields": fields,
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": footer_text},
                ],
            },
        ]

        fallback_text = f"{escaped_title} ({escaped_date}) at {ao_str}"
        return fallback_text, blocks

    @classmethod
    def _dispatch_slack_request(
        cls, api_url: str, token: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Execute an authenticated POST request to Slack Web API and return parsed JSON on success."""
        data_encoded = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=api_url,
            data=data_encoded,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                res_data: dict[str, Any] = json.loads(body)
                if not res_data.get("ok"):
                    logger.warning("Failed Slack API call (%s): %s", api_url, res_data.get("error"))
                    return None
                return res_data
        except urllib.error.HTTPError as http_err:
            error_body = ""
            try:
                error_body = http_err.read().decode("utf-8", errors="replace")[:256]
            except Exception:
                pass
            logger.warning(
                "HTTP error dispatching Slack notification (%s): %s - %s",
                api_url,
                http_err,
                error_body,
            )
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            logger.warning("Network error dispatching Slack notification (%s): %s", api_url, err)
            return None
        except Exception as err:
            logger.error("Unexpected error dispatching Slack notification (%s): %s", api_url, err)
            return None

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
        fng_names: list[str] | None = None,
        dr_names: list[str] | None = None,
        summary: str | None = None,
    ) -> str | None:
        """Post a structured Block Kit message summarizing a workout backblast and return the Slack 'ts'."""
        settings = get_settings()
        if not settings.slack_bot_token or not settings.slack_backblast_channel_id:
            logger.info("Slack notifications not configured; skipping channel post.")
            return None

        fallback_text, blocks = cls._build_backblast_message(
            title=title,
            workout_date=workout_date,
            url=url,
            author=author,
            aos=aos,
            q_names=q_names,
            pax_names=pax_names,
            fng_names=fng_names,
            dr_names=dr_names,
            backblast_url_prefix=settings.backblast_url_prefix,
            summary=summary,
        )

        payload: dict[str, Any] = {
            "channel": settings.slack_backblast_channel_id,
            "text": fallback_text,
            "blocks": blocks,
        }

        res_data = cls._dispatch_slack_request(
            api_url="https://slack.com/api/chat.postMessage",
            token=settings.slack_bot_token,
            payload=payload,
        )
        if not res_data:
            return None

        ts = res_data.get("ts")
        if not ts and isinstance(res_data.get("message"), dict):
            ts = res_data["message"].get("ts")
        return str(ts) if ts else None

    @classmethod
    @timed_service
    def update_backblast_summary(
        cls,
        slack_ts: str,
        title: str,
        workout_date: str,
        url: str | None,
        author: str | None,
        aos: list[str],
        q_names: list[str],
        pax_names: list[str],
        fng_names: list[str] | None = None,
        dr_names: list[str] | None = None,
        summary: str | None = None,
    ) -> bool:
        """Update an existing Slack backblast message in-place via chat.update using its 'ts'."""
        settings = get_settings()
        if not settings.slack_bot_token or not settings.slack_backblast_channel_id or not slack_ts:
            logger.info("Slack notifications or message ts not configured; skipping channel update.")
            return False

        fallback_text, blocks = cls._build_backblast_message(
            title=title,
            workout_date=workout_date,
            url=url,
            author=author,
            aos=aos,
            q_names=q_names,
            pax_names=pax_names,
            fng_names=fng_names,
            dr_names=dr_names,
            backblast_url_prefix=settings.backblast_url_prefix,
            summary=summary,
        )

        payload: dict[str, Any] = {
            "channel": settings.slack_backblast_channel_id,
            "ts": slack_ts,
            "text": fallback_text,
            "blocks": blocks,
        }

        res_data = cls._dispatch_slack_request(
            api_url="https://slack.com/api/chat.update",
            token=settings.slack_bot_token,
            payload=payload,
        )
        return res_data is not None

    @staticmethod
    def _append_bullet_sections(
        blocks: list[dict[str, Any]], heading: str, lines: list[str], max_chars: int = 2800
    ) -> None:
        """Append one or more mrkdwn section blocks for bullet lines, respecting Slack's 3000-char limit."""
        if not lines:
            return

        current_chunk = heading
        for line in lines:
            candidate = f"{current_chunk}\n{line}" if current_chunk else line
            if len(candidate) > max_chars and current_chunk:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": current_chunk},
                    }
                )
                current_chunk = line
            else:
                current_chunk = candidate

        if current_chunk:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": current_chunk},
                }
            )

    @classmethod
    def _build_weekly_digest_message(
        cls,
        start_date: str,
        end_date: str,
        workout_count: int,
        total_pax_appearances: int,
        unique_pax: int,
        fng_count: int,
        highlight_items: list[dict[str, str | None]],
        announcements: list[str],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build sanitized fallback text and Block Kit blocks for the weekly #1st-f-fitness digest."""
        escaped_start = _escape_mrkdwn(start_date)
        escaped_end = _escape_mrkdwn(end_date)
        header_title = f"*F3 RVA Weekly Summary* ({escaped_start} to {escaped_end})"
        stats_line = (
            f"*Workouts:* {workout_count}  |  "
            f"*Total PAX:* {total_pax_appearances}  |  "
            f"*Unique PAX:* {unique_pax}  |  "
            f"*FNGs:* {fng_count}"
        )

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header_title},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": stats_line}],
            },
        ]

        highlight_lines: list[str] = []
        for item in highlight_items:
            raw_text = (item.get("text") or "").strip()
            if not raw_text:
                continue
            escaped_bullet = _escape_mrkdwn(raw_text)
            raw_title = (item.get("title") or "").strip()
            raw_url = (item.get("url") or "").strip()
            if raw_title and _is_safe_url(raw_url):
                escaped_link_title = _escape_mrkdwn(raw_title)
                highlight_lines.append(f"• {escaped_bullet} (<{raw_url}|*{escaped_link_title}*>)")
            elif raw_title:
                escaped_link_title = _escape_mrkdwn(raw_title)
                highlight_lines.append(f"• {escaped_bullet} (*{escaped_link_title}*)")
            else:
                highlight_lines.append(f"• {escaped_bullet}")

        if highlight_lines:
            blocks.append({"type": "divider"})
            cls._append_bullet_sections(blocks, "*Workout Highlights*", highlight_lines)

        announcement_lines = [
            f"• {_escape_mrkdwn(a.strip())}" for a in announcements if a and a.strip()
        ]
        if announcement_lines:
            blocks.append({"type": "divider"})
            cls._append_bullet_sections(
                blocks, "*Announcements & Upcoming Events*", announcement_lines
            )

        fallback_text = (
            f"F3 RVA Weekly Summary ({escaped_start} to {escaped_end}) — "
            f"{workout_count} workouts, {total_pax_appearances} total PAX"
        )
        return fallback_text, blocks

    @classmethod
    @timed_service
    def post_weekly_digest(
        cls,
        start_date: str,
        end_date: str,
        workout_count: int,
        total_pax_appearances: int,
        unique_pax: int,
        fng_count: int,
        highlight_items: list[dict[str, str | None]],
        announcements: list[str],
    ) -> str | None:
        """Post the weekly workout and announcement digest to #1st-f-fitness and return Slack 'ts'."""
        settings = get_settings()
        if not settings.slack_bot_token or not settings.slack_fitness_channel_id:
            logger.info("Slack fitness channel not configured; skipping weekly digest post.")
            return None

        fallback_text, blocks = cls._build_weekly_digest_message(
            start_date=start_date,
            end_date=end_date,
            workout_count=workout_count,
            total_pax_appearances=total_pax_appearances,
            unique_pax=unique_pax,
            fng_count=fng_count,
            highlight_items=highlight_items,
            announcements=announcements,
        )

        payload: dict[str, Any] = {
            "channel": settings.slack_fitness_channel_id,
            "text": fallback_text,
            "blocks": blocks,
        }

        res_data = cls._dispatch_slack_request(
            api_url="https://slack.com/api/chat.postMessage",
            token=settings.slack_bot_token,
            payload=payload,
        )
        if not res_data:
            return None

        ts = res_data.get("ts")
        if not ts and isinstance(res_data.get("message"), dict):
            ts = res_data["message"].get("ts")
        return str(ts) if ts else None
