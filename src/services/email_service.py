"""Email notification service using AWS SES for alias requests and approvals."""

from __future__ import annotations

import html
import logging
import os
from typing import Any

from src.config.settings import get_settings
from src.models.schemas import MemberSummary
from src.utils.logging import timed_service

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[assignment]

logger = logging.getLogger("f3rva.services")


class EmailService:
    """Service for dispatching transactional email notifications via AWS Simple Email Service (SES)."""

    @classmethod
    def _get_base_site_url(cls) -> str:
        """Resolve public website base URL from settings or environment."""
        settings = get_settings()
        if settings.backblast_url_prefix:
            return settings.backblast_url_prefix.rstrip("/")
        env = (settings.environment or "development").lower()
        if env in ("production", "prod"):
            return "https://f3rva.org"
        return "https://dev.f3rva.org"

    @classmethod
    def _send_ses_email(
        cls,
        *,
        source: str,
        to_addresses: list[str],
        subject: str,
        html_body: str,
        text_body: str,
        reply_to_addresses: list[str] | None = None,
    ) -> bool:
        """Send an email via AWS SES with fault-tolerant exception handling."""
        if boto3 is None:
            logger.debug("boto3 is not available; skipping SES email send.")
            return False

        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        try:
            ses = boto3.client("ses", region_name=region)
            kwargs: dict[str, Any] = {
                "Source": source,
                "Destination": {"ToAddresses": to_addresses},
                "Message": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            }
            if reply_to_addresses:
                kwargs["ReplyToAddresses"] = reply_to_addresses

            ses.send_email(**kwargs)
            return True
        except Exception as exc:
            logger.error("Failed to send SES email to %s: %s", to_addresses, exc)
            return False

    @classmethod
    @timed_service
    def send_alias_request_admin_notification(
        cls,
        primary_member: MemberSummary,
        alias_member: MemberSummary,
        requestor_email: str | None = None,
    ) -> bool:
        """Notify admin email when a new member alias claim request is submitted."""
        settings = get_settings()
        if settings.environment == "testing" or not settings.admin_email:
            logger.debug("Skipping admin alias request email (environment=%s, admin_email=%s).", settings.environment, bool(settings.admin_email))
            return False

        admin_email = settings.admin_email.strip()
        if not admin_email:
            return False

        base_url = cls._get_base_site_url()
        admin_portal_url = f"{base_url}/bigdata/admin"

        safe_primary_name = html.escape(primary_member.f3_name)
        safe_alias_name = html.escape(alias_member.f3_name)
        safe_requestor_email = html.escape(requestor_email) if requestor_email else "Not available"
        safe_admin_url = html.escape(admin_portal_url, quote=True)

        subject = f"[F3 RVA] New Alias Claim Request: {alias_member.f3_name} -> {primary_member.f3_name}"

        text_body = (
            "A new F3 RVA alias claim request has been submitted and is awaiting administrator review.\n\n"
            f"Primary PAX: {primary_member.f3_name} (ID: {primary_member.member_id})\n"
            f"Requested Alias PAX: {alias_member.f3_name} (ID: {alias_member.member_id})\n"
            f"Requestor Email: {requestor_email or 'Not available'}\n\n"
            f"Review and approve or reject this request in the Admin Portal:\n{admin_portal_url}\n"
        )

        html_body = (
            "<html><body>"
            "<h2>New F3 RVA Alias Claim Request</h2>"
            "<p>A new member alias claim request has been submitted and is awaiting administrator review:</p>"
            "<ul>"
            f"<li><strong>Primary PAX:</strong> {safe_primary_name} (ID: {primary_member.member_id})</li>"
            f"<li><strong>Requested Alias PAX:</strong> {safe_alias_name} (ID: {alias_member.member_id})</li>"
            f"<li><strong>Requestor Email:</strong> {safe_requestor_email}</li>"
            "</ul>"
            f'<p><a href="{safe_admin_url}">Review Pending Requests in the F3 RVA Admin Portal</a></p>'
            "</body></html>"
        )

        reply_to = [requestor_email.strip()] if requestor_email and requestor_email.strip() else None
        return cls._send_ses_email(
            source=admin_email,
            to_addresses=[admin_email],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to_addresses=reply_to,
        )

    @classmethod
    @timed_service
    def send_alias_request_receipt_notification(
        cls,
        primary_member: MemberSummary,
        alias_member: MemberSummary,
        recipient_email: str,
    ) -> bool:
        """Send confirmation email to the requestor indicating their alias request was received and is pending."""
        settings = get_settings()
        if settings.environment == "testing" or not settings.admin_email:
            logger.debug("Skipping requestor receipt email (environment=%s, admin_email=%s).", settings.environment, bool(settings.admin_email))
            return False

        admin_email = settings.admin_email.strip()
        clean_recipient = recipient_email.strip()
        if not admin_email or not clean_recipient:
            return False

        safe_primary_name = html.escape(primary_member.f3_name)
        safe_alias_name = html.escape(alias_member.f3_name)

        subject = f"[F3 RVA] Alias Request Received: {alias_member.f3_name} -> {primary_member.f3_name}"

        text_body = (
            f"{primary_member.f3_name},\n\n"
            f"We have received your request to link the alias '{alias_member.f3_name}' (ID: {alias_member.member_id}) "
            f"to your primary F3 RVA profile '{primary_member.f3_name}' (ID: {primary_member.member_id}).\n\n"
            "Status: Pending Administrator Review\n\n"
            "You will receive another email confirmation as soon as an administrator approves your request and merges your workout history.\n\n"
        )

        html_body = (
            "<html><body>"
            "<h2>F3 RVA Alias Claim Request Received</h2>"
            f"<p><strong>{safe_primary_name}</strong>,</p>"
            "<p>We have received your request to claim and merge the following alias into your primary profile:</p>"
            "<ul>"
            f"<li><strong>Primary PAX Profile:</strong> {safe_primary_name} (ID: {primary_member.member_id})</li>"
            f"<li><strong>Requested Alias:</strong> {safe_alias_name} (ID: {alias_member.member_id})</li>"
            "<li><strong>Status:</strong> Pending Administrator Review</li>"
            "</ul>"
            "<p>You will receive a confirmation email once an administrator reviews and approves your request.</p>"
            "</body></html>"
        )

        return cls._send_ses_email(
            source=admin_email,
            to_addresses=[clean_recipient],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    @classmethod
    @timed_service
    def send_alias_approved_notification(
        cls,
        primary_member: MemberSummary,
        alias_member: MemberSummary,
        recipient_email: str,
    ) -> bool:
        """Send confirmation email to the requestor when an administrator approves their alias request."""
        settings = get_settings()
        if settings.environment == "testing" or not settings.admin_email:
            logger.debug("Skipping requestor approval email (environment=%s, admin_email=%s).", settings.environment, bool(settings.admin_email))
            return False

        admin_email = settings.admin_email.strip()
        clean_recipient = recipient_email.strip()
        if not admin_email or not clean_recipient:
            return False

        base_url = cls._get_base_site_url()
        pax_profile_url = f"{base_url}/bigdata/pax/{primary_member.member_id}"

        safe_primary_name = html.escape(primary_member.f3_name)
        safe_alias_name = html.escape(alias_member.f3_name)
        safe_profile_url = html.escape(pax_profile_url, quote=True)

        subject = f"[F3 RVA] Alias Request Approved: {alias_member.f3_name} merged into {primary_member.f3_name}"

        text_body = (
            f"{primary_member.f3_name},\n\n"
            f"Your F3 RVA alias request has been approved! The alias '{alias_member.f3_name}' "
            f"has been merged into your primary profile '{primary_member.f3_name}'.\n\n"
            "All associated workout attendance and Q records have been consolidated under your primary profile.\n\n"
            f"View your updated PAX stats: {pax_profile_url}\n"
        )

        html_body = (
            "<html><body>"
            "<h2>F3 RVA Alias Request Approved</h2>"
            f"<p><strong>{safe_primary_name}</strong>,</p>"
            f"<p>Your alias claim request has been <strong>approved</strong>! The alias <strong>{safe_alias_name}</strong> "
            f"has been merged into your primary F3 RVA profile <strong>{safe_primary_name}</strong>.</p>"
            "<p>All associated workout attendance and Q records have been consolidated under your primary profile.</p>"
            f'<p><a href="{safe_profile_url}">View Your Updated PAX Profile &amp; Stats</a></p>'
            "</body></html>"
        )

        return cls._send_ses_email(
            source=admin_email,
            to_addresses=[clean_recipient],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    @classmethod
    @timed_service
    def send_alias_rejected_notification(
        cls,
        primary_member: MemberSummary,
        alias_member: MemberSummary,
        recipient_email: str,
    ) -> bool:
        """Send notification email to the requestor when an administrator rejects their alias request."""
        settings = get_settings()
        if settings.environment == "testing" or not settings.admin_email:
            logger.debug("Skipping requestor rejection email (environment=%s, admin_email=%s).", settings.environment, bool(settings.admin_email))
            return False

        admin_email = settings.admin_email.strip()
        clean_recipient = recipient_email.strip()
        if not admin_email or not clean_recipient:
            return False

        safe_primary_name = html.escape(primary_member.f3_name)
        safe_alias_name = html.escape(alias_member.f3_name)
        safe_admin_email = html.escape(admin_email)

        subject = f"[F3 RVA] Alias Request Not Approved: {alias_member.f3_name} -> {primary_member.f3_name}"

        text_body = (
            f"{primary_member.f3_name},\n\n"
            f"Your F3 RVA alias request to merge '{alias_member.f3_name}' (ID: {alias_member.member_id}) "
            f"into your primary profile '{primary_member.f3_name}' (ID: {primary_member.member_id}) was not approved.\n\n"
            f"If you believe this was in error or have questions, please reply to this email ({admin_email}) or reach out in Slack.\n"
        )

        html_body = (
            "<html><body>"
            "<h2>F3 RVA Alias Request Update</h2>"
            f"<p><strong>{safe_primary_name}</strong>,</p>"
            f"<p>Your alias claim request to merge <strong>{safe_alias_name}</strong> (ID: {alias_member.member_id}) "
            f"into your primary F3 RVA profile <strong>{safe_primary_name}</strong> (ID: {primary_member.member_id}) was <strong>not approved</strong>.</p>"
            f'<p>If you believe this was in error or have questions, please reply to this email (<a href="mailto:{safe_admin_email}">{safe_admin_email}</a>) or reach out in Slack.</p>'
            "</body></html>"
        )

        return cls._send_ses_email(
            source=admin_email,
            to_addresses=[clean_recipient],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )


