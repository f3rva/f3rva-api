"""Unit and Integration Tests for Slack OAuth Authentication and Profile Linking."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.workout import AO, Member, MemberAlias, MemberSlack
from src.utils.security import create_access_token


def test_get_all_aos_endpoint(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/workouts/aos returns list of all registered AOs."""
    db_session.add(AO(description="First Watch", slug="first-watch"))
    db_session.add(AO(description="Gridiron", slug="gridiron"))
    db_session.commit()

    res = client.get("/v2/workouts/aos")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["description"] == "First Watch"
    assert data[1]["description"] == "Gridiron"


def test_slack_exchange_missing_credentials_500(client: TestClient) -> None:
    """Verify POST /v2/auth/slack returns 500 if Slack credentials are not configured."""
    with patch("src.services.slack_auth_service.get_settings") as mock_settings:
        mock_settings.return_value.slack_client_id = None
        mock_settings.return_value.slack_client_secret = None
        res = client.post("/v2/auth/slack", json={"code": "123", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 500
        assert res.json()["errorCode"] == 5001


def test_slack_exchange_network_error_502(client: TestClient) -> None:
    """Verify POST /v2/auth/slack returns 502 when Slack OAuth server is unreachable."""
    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        mock_settings.return_value.slack_client_id = "test_client_id"
        mock_settings.return_value.slack_client_secret = "test_client_secret"
        res = client.post("/v2/auth/slack", json={"code": "123", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 502
        assert res.json()["errorCode"] == 5002


def test_slack_exchange_slack_error_400(client: TestClient) -> None:
    """Verify POST /v2/auth/slack returns 400 when Slack returns an OAuth error."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": false, "error": "invalid_code"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=mock_resp):
        mock_settings.return_value.slack_client_id = "test_client_id"
        mock_settings.return_value.slack_client_secret = "test_client_secret"
        res = client.post("/v2/auth/slack", json={"code": "bad_code", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 400
        assert res.json()["errorCode"] == 5003


def test_slack_exchange_unauthorized_workspace_403(client: TestClient) -> None:
    """Verify POST /v2/auth/slack returns 403 when user belongs to unauthorized workspace."""
    token_resp = MagicMock()
    token_resp.read.return_value = b'{"ok": true, "access_token": "xoxp-123", "id_token": "a.eyJzdWIiOiAiVTEyMyIsICJodHRwczovL3NsYWNrLmNvbS90ZWFtX2lkIjogIlRfV1JPTkciLCAiaHR0cHM6Ly9zbGFjay5jb20vdXNlcl9pZCI6ICJVMTIzIiwgIm5hbWUiOiAiQXR0aWxhIn0=.c"}'
    token_resp.__enter__.return_value = token_resp

    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=token_resp):
        mock_settings.return_value.slack_client_id = "test_client_id"
        mock_settings.return_value.slack_client_secret = "test_client_secret"
        mock_settings.return_value.slack_allowed_team_id = "T_ALLOWED_123"

        res = client.post("/v2/auth/slack", json={"code": "valid_code", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 403
        assert res.json()["errorCode"] == 4003


def test_slack_login_already_linked_direct_jwt(client: TestClient, db_session: Session) -> None:
    """Verify linked Slack user receives direct JWT session without confirmation prompt."""
    member = Member(f3_name="Attila")
    db_session.add(member)
    db_session.flush()

    db_session.add(
        MemberSlack(
            member_id=member.member_id,
            slack_team_id="T_PROD",
            slack_user_id="U_ATTILA",
            slack_display_name="Attila",
        )
    )
    db_session.commit()

    token_resp = MagicMock()
    token_resp.read.return_value = b'{"ok": true, "access_token": "xoxp-123", "id_token": "a.eyJzdWIiOiAiVV9BVFRJTEEiLCAiaHR0cHM6Ly9zbGFjay5jb20vdGVhbV9pZCI6ICJUX1BST0QiLCAiaHR0cHM6Ly9zbGFjay5jb20vdXNlcl9pZCI6ICJVX0FUVElMQSIsICJuYW1lIjogIkF0dGlsYSJ9.c"}'
    token_resp.__enter__.return_value = token_resp

    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=token_resp):
        mock_settings.return_value.slack_client_id = "client_id"
        mock_settings.return_value.slack_client_secret = "client_secret"
        mock_settings.return_value.slack_allowed_team_id = "T_PROD"

        res = client.post("/v2/auth/slack", json={"code": "valid_code", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 200
        data = res.json()
        assert data["isLinked"] is True
        assert data["accessToken"] is not None
        assert data["expiresIn"] == 5184000
        assert data["user"]["f3Name"] == "Attila"
        assert data["user"]["memberId"] == member.member_id


def test_slack_login_unlinked_with_suggested_member(client: TestClient, db_session: Session) -> None:
    """Verify unlinked Slack user receives suggestion and temporary link token."""
    member = Member(f3_name="Dingo")
    db_session.add(member)
    db_session.commit()

    token_resp = MagicMock()
    token_resp.read.return_value = b'{"ok": true, "access_token": "xoxp-123", "id_token": "a.eyJzdWIiOiAiVV9ESU5HTyIsICJodHRwczovL3NsYWNrLmNvbS90ZWFtX2lkIjogIlRfUFJPRCIsICJodHRwczovL3NsYWNrLmNvbS91c2VyX2lkIjogIlVfRElOR08iLCAibmFtZSI6ICJEaW5nbyJ9.c"}'
    token_resp.__enter__.return_value = token_resp

    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=token_resp):
        mock_settings.return_value.slack_client_id = "client_id"
        mock_settings.return_value.slack_client_secret = "client_secret"
        mock_settings.return_value.slack_allowed_team_id = "T_PROD"

        res = client.post("/v2/auth/slack", json={"code": "valid_code", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 200
        data = res.json()
        assert data["isLinked"] is False
        assert data["suggestedMember"]["f3Name"] == "Dingo"
        assert data["suggestedMember"]["memberId"] == member.member_id
        assert data["tempToken"] is not None


def test_slack_login_unlinked_alias_suggestion(client: TestClient, db_session: Session) -> None:
    """Verify unlinked Slack user matching an alias receives primary member suggestion."""
    primary = Member(f3_name="Robert")
    db_session.add(primary)
    db_session.flush()
    db_session.add(MemberAlias(member_id=primary.member_id, f3_alias="Bob"))
    db_session.commit()

    token_resp = MagicMock()
    token_resp.read.return_value = b'{"ok": true, "access_token": "xoxp-123", "id_token": "a.eyJzdWIiOiAiVV9CT0IiLCAiaHR0cHM6Ly9zbGFjay5jb20vdGVhbV9pZCI6ICJUX1BST0QiLCAiaHR0cHM6Ly9zbGFjay5jb20vdXNlcl9pZCI6ICJVX0JPQiIsICJuYW1lIjogIkJvYiJ9.c"}'
    token_resp.__enter__.return_value = token_resp

    with patch("src.services.slack_auth_service.get_settings") as mock_settings, \
         patch("urllib.request.urlopen", return_value=token_resp):
        mock_settings.return_value.slack_client_id = "client_id"
        mock_settings.return_value.slack_client_secret = "client_secret"
        mock_settings.return_value.slack_allowed_team_id = "T_PROD"

        res = client.post("/v2/auth/slack", json={"code": "valid_code", "redirectUri": "http://localhost/callback"})
        assert res.status_code == 200
        data = res.json()
        assert data["isLinked"] is False
        assert data["suggestedMember"]["f3Name"] == "Robert"
        assert data["suggestedMember"]["memberId"] == primary.member_id


def test_confirm_slack_link_success(client: TestClient, db_session: Session) -> None:
    """Verify POST /v2/auth/slack/confirm-link links user in MEMBER_SLACK and issues session JWT."""
    member = Member(f3_name="Swag")
    db_session.add(member)
    db_session.commit()

    temp_token = create_access_token(
        data={
            "sub": "U_SWAG_123",
            "team_id": "T_PROD",
            "display_name": "Swag",
            "real_name": "Dave",
            "email": "swag@example.com",
            "type": "slack_temp_link",
        }
    )

    res = client.post(
        "/v2/auth/slack/confirm-link",
        json={"tempToken": temp_token, "memberId": member.member_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["isLinked"] is True
    assert data["accessToken"] is not None
    assert data["expiresIn"] == 5184000
    assert data["user"]["f3Name"] == "Swag"
    assert data["user"]["memberId"] == member.member_id

    # Verify DB record
    record = db_session.query(MemberSlack).filter_by(slack_team_id="T_PROD", slack_user_id="U_SWAG_123").first()
    assert record is not None
    assert record.member_id == member.member_id
    assert record.slack_display_name == "Swag"


def test_confirm_slack_link_invalid_token(client: TestClient) -> None:
    """Verify POST /v2/auth/slack/confirm-link rejects non-temp tokens with 400."""
    wrong_token = create_access_token(data={"sub": "U123", "role": "member"})
    res = client.post(
        "/v2/auth/slack/confirm-link",
        json={"tempToken": wrong_token, "memberId": 1},
    )
    assert res.status_code == 400
    assert res.json()["errorCode"] == 4010


def test_confirm_slack_link_member_not_found(client: TestClient) -> None:
    """Verify POST /v2/auth/slack/confirm-link returns 404 when member ID does not exist."""
    temp_token = create_access_token(
        data={
            "sub": "U_999",
            "team_id": "T_PROD",
            "type": "slack_temp_link",
        }
    )
    res = client.post(
        "/v2/auth/slack/confirm-link",
        json={"tempToken": temp_token, "memberId": 99999},
    )
    assert res.status_code == 404
    assert res.json()["errorCode"] == 2001


def test_get_current_user_profile_member_success(client: TestClient, db_session: Session) -> None:
    """Verify GET /v2/auth/me returns active member profile."""
    member = Member(f3_name="Splinter")
    db_session.add(member)
    db_session.commit()

    token = create_access_token(
        data={"sub": "U_SPLINTER", "member_id": member.member_id, "f3_name": "Splinter", "role": "member"}
    )
    res = client.get("/v2/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["memberId"] == member.member_id
    assert data["f3Name"] == "Splinter"
    assert data["role"] == "member"


def test_get_current_user_profile_admin_success(client: TestClient) -> None:
    """Verify GET /v2/auth/me returns admin profile."""
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    res = client.get("/v2/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["f3Name"] == "admin"
    assert data["role"] == "admin"


def test_get_current_user_profile_missing_token_401(client: TestClient) -> None:
    """Verify GET /v2/auth/me returns 401 without Bearer token."""
    res = client.get("/v2/auth/me")
    assert res.status_code == 401
    assert res.json()["errorCode"] == 4010
