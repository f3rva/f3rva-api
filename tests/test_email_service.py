"""Unit tests for EmailService and alias notification triggers."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.models.schemas import MemberSummary
from src.models.workout import Member, MemberSlack
from src.services.alias_service import AliasService
from src.services.email_service import EmailService


def _mock_settings(
    mocker: Any,
    *,
    environment: str = "development",
    admin_email: str | None = "admin@dev.f3rva.org",
    backblast_url_prefix: str | None = "https://dev.f3rva.org",
) -> Settings:
    """Create and patch a Settings instance for email unit tests."""
    mock_cfg = Settings(
        environment=environment,
        admin_email=admin_email,
        backblast_url_prefix=backblast_url_prefix,
    )
    mocker.patch("src.services.email_service.get_settings", return_value=mock_cfg)
    return mock_cfg


def test_send_alias_request_admin_notification_success(mocker: Any) -> None:
    """Verify SES send_email is invoked with admin email, Reply-To, and escaped HTML on new alias request."""
    _mock_settings(
        mocker,
        environment="development",
        admin_email="admin@dev.f3rva.org",
        backblast_url_prefix="https://dev.f3rva.org",
    )
    mock_ses = MagicMock()
    mock_boto_client = mocker.patch("src.services.email_service.boto3.client", return_value=mock_ses)

    primary = MemberSummary(memberId=10, f3Name="Dredd <Leader>")
    alias = MemberSummary(memberId=20, f3Name="OBT & Co")

    sent = EmailService.send_alias_request_admin_notification(
        primary_member=primary,
        alias_member=alias,
        requestor_email="dredd@example.com",
    )

    assert sent is True
    mock_boto_client.assert_called_once_with("ses", region_name="us-east-1")
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["Source"] == "admin@dev.f3rva.org"
    assert call_kwargs["Destination"] == {"ToAddresses": ["admin@dev.f3rva.org"]}
    assert call_kwargs["ReplyToAddresses"] == ["dredd@example.com"]
    assert "[F3 RVA] New Alias Claim Request: OBT & Co -> Dredd <Leader>" in call_kwargs["Message"]["Subject"]["Data"]
    html_body = call_kwargs["Message"]["Body"]["Html"]["Data"]
    assert "Dredd &lt;Leader&gt;" in html_body
    assert "OBT &amp; Co" in html_body
    assert "https://dev.f3rva.org/bigdata/admin" in html_body


def test_send_alias_request_receipt_notification_success(mocker: Any) -> None:
    """Verify SES send_email is invoked to send pending confirmation receipt to requestor."""
    _mock_settings(
        mocker,
        environment="production",
        admin_email="admin@f3rva.org",
        backblast_url_prefix="https://f3rva.org",
    )
    mock_ses = MagicMock()
    mocker.patch("src.services.email_service.boto3.client", return_value=mock_ses)

    primary = MemberSummary(memberId=10, f3Name="Dredd")
    alias = MemberSummary(memberId=20, f3Name="Dredd_Old")

    sent = EmailService.send_alias_request_receipt_notification(
        primary_member=primary,
        alias_member=alias,
        recipient_email="dredd@example.com",
    )

    assert sent is True
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["Source"] == "admin@f3rva.org"
    assert call_kwargs["Destination"] == {"ToAddresses": ["dredd@example.com"]}
    assert "Alias Request Received" in call_kwargs["Message"]["Subject"]["Data"]
    assert "Pending Administrator Review" in call_kwargs["Message"]["Body"]["Html"]["Data"]


def test_send_alias_approved_notification_success(mocker: Any) -> None:
    """Verify SES send_email is invoked to notify requestor when alias request is approved."""
    _mock_settings(
        mocker,
        environment="production",
        admin_email="admin@f3rva.org",
        backblast_url_prefix=None,
    )
    mock_ses = MagicMock()
    mocker.patch("src.services.email_service.boto3.client", return_value=mock_ses)

    primary = MemberSummary(memberId=10, f3Name="Dredd")
    alias = MemberSummary(memberId=20, f3Name="Dredd_Old")

    sent = EmailService.send_alias_approved_notification(
        primary_member=primary,
        alias_member=alias,
        recipient_email="dredd@example.com",
    )

    assert sent is True
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["Source"] == "admin@f3rva.org"
    assert call_kwargs["Destination"] == {"ToAddresses": ["dredd@example.com"]}
    assert "Alias Request Approved" in call_kwargs["Message"]["Subject"]["Data"]
    assert "https://f3rva.org/bigdata/pax/10" in call_kwargs["Message"]["Body"]["Html"]["Data"]


def test_send_alias_rejected_notification_success(mocker: Any) -> None:
    """Verify SES send_email is invoked to notify requestor when alias request is rejected."""
    _mock_settings(
        mocker,
        environment="development",
        admin_email="admin@dev.f3rva.org",
        backblast_url_prefix="https://dev.f3rva.org",
    )
    mock_ses = MagicMock()
    mocker.patch("src.services.email_service.boto3.client", return_value=mock_ses)

    primary = MemberSummary(memberId=10, f3Name="Dredd")
    alias = MemberSummary(memberId=20, f3Name="WrongAlias")

    sent = EmailService.send_alias_rejected_notification(
        primary_member=primary,
        alias_member=alias,
        recipient_email="dredd@example.com",
    )

    assert sent is True
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["Source"] == "admin@dev.f3rva.org"
    assert call_kwargs["Destination"] == {"ToAddresses": ["dredd@example.com"]}
    assert "Alias Request Not Approved" in call_kwargs["Message"]["Subject"]["Data"]
    assert "not approved" in call_kwargs["Message"]["Body"]["Html"]["Data"]
    assert "mailto:admin@dev.f3rva.org" in call_kwargs["Message"]["Body"]["Html"]["Data"]


def test_email_service_skips_in_testing_or_missing_admin_email(mocker: Any) -> None:
    """Verify EmailService returns False without calling boto3 in testing environment or when admin_email is None."""
    mock_boto_client = mocker.patch("src.services.email_service.boto3.client")
    primary = MemberSummary(memberId=1, f3Name="PaxA")
    alias = MemberSummary(memberId=2, f3Name="PaxB")

    # 1. Testing environment
    _mock_settings(mocker, environment="testing", admin_email="admin@dev.f3rva.org")
    assert EmailService.send_alias_request_admin_notification(primary, alias) is False
    assert EmailService.send_alias_request_receipt_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_approved_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_rejected_notification(primary, alias, "a@b.com") is False

    # 2. Missing admin_email
    _mock_settings(mocker, environment="development", admin_email=None)
    assert EmailService.send_alias_request_admin_notification(primary, alias) is False
    assert EmailService.send_alias_request_receipt_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_approved_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_rejected_notification(primary, alias, "a@b.com") is False

    # 3. Whitespace-only admin_email or recipient
    _mock_settings(mocker, environment="development", admin_email="   ")
    assert EmailService.send_alias_request_admin_notification(primary, alias) is False
    assert EmailService.send_alias_request_receipt_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_approved_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_rejected_notification(primary, alias, "a@b.com") is False

    mock_boto_client.assert_not_called()


def test_email_service_handles_ses_exception_gracefully(mocker: Any) -> None:
    """Verify SES errors are caught and logged without raising exceptions."""
    _mock_settings(mocker, environment="development", admin_email="admin@dev.f3rva.org", backblast_url_prefix=None)
    mock_ses = MagicMock()
    mock_ses.send_email.side_effect = RuntimeError("SES sandbox rejection")
    mocker.patch("src.services.email_service.boto3.client", return_value=mock_ses)

    primary = MemberSummary(memberId=1, f3Name="PaxA")
    alias = MemberSummary(memberId=2, f3Name="PaxB")

    assert EmailService.send_alias_request_admin_notification(primary, alias) is False
    assert EmailService.send_alias_request_receipt_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_approved_notification(primary, alias, "a@b.com") is False
    assert EmailService.send_alias_rejected_notification(primary, alias, "a@b.com") is False


def test_email_service_handles_missing_boto3(mocker: Any) -> None:
    """Verify _send_ses_email returns False when boto3 is None."""
    _mock_settings(mocker, environment="development", admin_email="admin@dev.f3rva.org")
    mocker.patch("src.services.email_service.boto3", None)

    primary = MemberSummary(memberId=1, f3Name="PaxA")
    alias = MemberSummary(memberId=2, f3Name="PaxB")
    assert EmailService.send_alias_request_admin_notification(primary, alias) is False


def test_alias_service_triggers_emails_on_request_approve_and_reject(db_session: Session, mocker: Any) -> None:
    """Verify AliasService.request_alias, approve_alias, and reject_alias trigger EmailService."""
    m1 = Member(member_id=101, f3_name="PrimaryPax", is_dr=False)
    m2 = Member(member_id=102, f3_name="AliasPax", is_dr=False)
    m3 = Member(member_id=103, f3_name="RejectedPax", is_dr=False)
    slack_link = MemberSlack(
        slack_team_id="T123",
        slack_user_id="U101",
        member_id=101,
        slack_display_name="PrimaryPax",
        slack_real_name="John Doe",
        slack_email="primary.pax@example.com",
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add_all([m1, m2, m3, slack_link])
    db_session.commit()

    mock_admin_email = mocker.patch.object(EmailService, "send_alias_request_admin_notification", return_value=True)
    mock_receipt_email = mocker.patch.object(EmailService, "send_alias_request_receipt_notification", return_value=True)
    mock_approved_email = mocker.patch.object(EmailService, "send_alias_approved_notification", return_value=True)
    mock_rejected_email = mocker.patch.object(EmailService, "send_alias_rejected_notification", return_value=True)

    # 1. Request alias (101 -> 102)
    req_res = AliasService.request_alias(db=db_session, primary_id=101, alias_id=102)
    assert req_res.status == "pending"

    mock_admin_email.assert_called_once_with(
        primary_member=MemberSummary(memberId=101, f3Name="PrimaryPax"),
        alias_member=MemberSummary(memberId=102, f3Name="AliasPax"),
        requestor_email="primary.pax@example.com",
    )
    mock_receipt_email.assert_called_once_with(
        primary_member=MemberSummary(memberId=101, f3Name="PrimaryPax"),
        alias_member=MemberSummary(memberId=102, f3Name="AliasPax"),
        recipient_email="primary.pax@example.com",
    )

    # 2. Approve alias (101 -> 102)
    app_res = AliasService.approve_alias(db=db_session, primary_id=101, alias_id=102)
    assert app_res.status == "approved"

    mock_approved_email.assert_called_once_with(
        primary_member=MemberSummary(memberId=101, f3Name="PrimaryPax"),
        alias_member=MemberSummary(memberId=102, f3Name="AliasPax"),
        recipient_email="primary.pax@example.com",
    )

    # 3. Request and Reject alias (101 -> 103)
    AliasService.request_alias(db=db_session, primary_id=101, alias_id=103)
    rej_res = AliasService.reject_alias(db=db_session, primary_id=101, alias_id=103)
    assert rej_res.status == "rejected"

    mock_rejected_email.assert_called_once_with(
        primary_member=MemberSummary(memberId=101, f3Name="PrimaryPax"),
        alias_member=MemberSummary(memberId=103, f3Name="RejectedPax"),
        recipient_email="primary.pax@example.com",
    )

    # 4. Re-request the previously rejected alias (101 -> 103), reject again, then re-request and approve
    AliasService.request_alias(db=db_session, primary_id=101, alias_id=103)
    rej_again = AliasService.reject_alias(db=db_session, primary_id=101, alias_id=103)
    assert rej_again.status == "rejected"

    AliasService.request_alias(db=db_session, primary_id=101, alias_id=103)
    app_after_rej = AliasService.approve_alias(db=db_session, primary_id=101, alias_id=103)
    assert app_after_rej.status == "approved"


