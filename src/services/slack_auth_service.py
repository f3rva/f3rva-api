"""Service handling Slack OAuth OIDC code exchange, member matching, and user session management."""

from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.schemas import (
    AuthUserProfile,
    MemberSummary,
    SlackAuthResponse,
    SlackUserProfile,
)
from src.models.workout import Member, MemberAlias, MemberSlack
from src.utils.logging import timed_service
from src.utils.security import create_access_token, decode_access_token

# Regular members enjoy a 60-day session lifespan
MEMBER_SESSION_DURATION = datetime.timedelta(days=60)
MEMBER_SESSION_EXPIRES_IN = int(MEMBER_SESSION_DURATION.total_seconds())  # 5,184,000 seconds


class SlackAuthService:
    """Business logic for Slack OAuth OIDC authentication and F3 member linking."""

    @classmethod
    @timed_service
    def exchange_code(cls, code: str, redirect_uri: str) -> SlackUserProfile:
        """Exchange authorization code with Slack for user profile and identity."""
        settings = get_settings()
        if not settings.slack_client_id or not settings.slack_client_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"errorCode": 5001, "errorMessage": "Slack OAuth credentials not configured."},
            )

        payload = {
            "client_id": settings.slack_client_id,
            "client_secret": settings.slack_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        data_encoded = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            url="https://slack.com/api/openid.connect.token",
            data=data_encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                token_data = json.loads(body)
        except urllib.error.URLError as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"errorCode": 5002, "errorMessage": f"Failed to contact Slack OAuth server: {err}."},
            ) from None

        if not token_data.get("ok"):
            error_msg = token_data.get("error", "Unknown Slack OAuth error")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 5003, "errorMessage": f"Slack OAuth exchange failed: {error_msg}."},
            )

        access_token = token_data.get("access_token")
        id_token_payload = cls._parse_id_token(token_data.get("id_token", ""))

        # Fetch detailed user profile via userInfo if token available
        user_info: dict[str, Any] = {}
        if access_token:
            user_info = cls._fetch_user_info(access_token)

        user_id = (
            user_info.get("https://slack.com/user_id")
            or id_token_payload.get("https://slack.com/user_id")
            or user_info.get("sub")
        )
        team_id = user_info.get("https://slack.com/team_id") or id_token_payload.get("https://slack.com/team_id")
        email = user_info.get("email") or id_token_payload.get("email")
        full_name = user_info.get("name") or id_token_payload.get("name") or "PAX"
        given_name = user_info.get("given_name") or id_token_payload.get("given_name")

        if not user_id or not team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 5004, "errorMessage": "Incomplete Slack identity received."},
            )

        # Enforce Workspace / Team ID restriction if configured
        if settings.slack_allowed_team_id and team_id != settings.slack_allowed_team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"errorCode": 4003, "errorMessage": "Access denied: Unauthorized Slack workspace."},
            )

        display_name = None
        real_name = full_name or given_name

        # If bot token is configured, query users.info to retrieve actual workspace display_name
        if settings.slack_bot_token and user_id:
            bot_user = cls._fetch_bot_user_profile(settings.slack_bot_token, user_id)
            if bot_user:
                profile = bot_user.get("profile", {})
                display_name = (
                    profile.get("display_name")
                    or profile.get("display_name_normalized")
                )
                real_name = profile.get("real_name") or bot_user.get("real_name") or real_name
                if not email:
                    email = profile.get("email")

        # Fallback priority for display_name
        if not display_name:
            display_name = (
                user_info.get("nickname")
                or user_info.get("preferred_username")
                or id_token_payload.get("nickname")
                or id_token_payload.get("preferred_username")
                or full_name
            )

        return SlackUserProfile(
            slackUserId=user_id,
            slackTeamId=team_id,
            displayName=display_name,
            realName=real_name,
            email=email,
        )

    @classmethod
    @timed_service
    def handle_slack_login(cls, db: Session, slack_user: SlackUserProfile) -> SlackAuthResponse:
        """Check if Slack user is linked in MEMBER_SLACK; if linked, issue JWT; otherwise suggest profile."""
        linked = db.execute(
            select(MemberSlack).where(
                MemberSlack.slack_team_id == slack_user.slack_team_id,
                MemberSlack.slack_user_id == slack_user.slack_user_id,
            )
        ).scalar_one_or_none()

        if linked:
            # Refresh cached metadata in MEMBER_SLACK
            linked.slack_display_name = slack_user.display_name
            linked.slack_real_name = slack_user.real_name
            linked.slack_email = slack_user.email
            linked.updated_at = datetime.datetime.now(datetime.UTC)
            db.commit()

            member = db.execute(
                select(Member).where(Member.member_id == linked.member_id)
            ).scalar_one_or_none()
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"errorCode": 2001, "errorMessage": f"Linked member {linked.member_id} not found."},
                )

            token = create_access_token(
                data={
                    "sub": slack_user.slack_user_id,
                    "member_id": member.member_id,
                    "f3_name": member.f3_name,
                    "role": "member",
                },
                expires_delta=MEMBER_SESSION_DURATION,
            )
            return SlackAuthResponse(
                isLinked=True,
                accessToken=token,
                tokenType="bearer",
                expiresIn=MEMBER_SESSION_EXPIRES_IN,
                user=AuthUserProfile(
                    memberId=member.member_id,
                    f3Name=member.f3_name,
                    slackUserId=slack_user.slack_user_id,
                    role="member",
                ),
            )

        # Unlinked first-time login: find suggestion for user confirmation
        suggested_member = cls._find_suggested_member(db, slack_user.display_name)

        # Generate short-lived temporary token (15 mins) for link confirmation
        temp_token = create_access_token(
            data={
                "sub": slack_user.slack_user_id,
                "team_id": slack_user.slack_team_id,
                "display_name": slack_user.display_name,
                "real_name": slack_user.real_name,
                "email": slack_user.email,
                "type": "slack_temp_link",
            },
            expires_delta=datetime.timedelta(minutes=15),
        )

        return SlackAuthResponse(
            isLinked=False,
            suggestedMember=suggested_member,
            slackUser=slack_user,
            tempToken=temp_token,
        )

    @classmethod
    @timed_service
    def confirm_member_link(cls, db: Session, temp_token: str, member_id: int) -> SlackAuthResponse:
        """Validate temp token, persist MEMBER_SLACK mapping, and issue full session JWT."""
        payload = decode_access_token(temp_token)
        if payload.get("type") != "slack_temp_link":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 4010, "errorMessage": "Invalid link confirmation token."},
            )

        slack_user_id = payload.get("sub")
        slack_team_id = payload.get("team_id")
        if not slack_user_id or not slack_team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": 4010, "errorMessage": "Missing Slack user identity in token."},
            )

        member = db.execute(
            select(Member).where(Member.member_id == member_id)
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errorCode": 2001, "errorMessage": f"Member ID {member_id} not found."},
            )

        # Check existing mapping or insert new
        existing = db.execute(
            select(MemberSlack).where(
                MemberSlack.slack_team_id == slack_team_id,
                MemberSlack.slack_user_id == slack_user_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.member_id = member_id
            existing.slack_display_name = payload.get("display_name")
            existing.slack_real_name = payload.get("real_name")
            existing.slack_email = payload.get("email")
            existing.updated_at = datetime.datetime.now(datetime.UTC)
        else:
            db.add(
                MemberSlack(
                    member_id=member_id,
                    slack_team_id=slack_team_id,
                    slack_user_id=slack_user_id,
                    slack_display_name=payload.get("display_name"),
                    slack_real_name=payload.get("real_name"),
                    slack_email=payload.get("email"),
                    updated_at=datetime.datetime.now(datetime.UTC),
                )
            )

        db.commit()

        token = create_access_token(
            data={
                "sub": slack_user_id,
                "member_id": member.member_id,
                "f3_name": member.f3_name,
                "role": "member",
            },
            expires_delta=MEMBER_SESSION_DURATION,
        )

        return SlackAuthResponse(
            isLinked=True,
            accessToken=token,
            tokenType="bearer",
            expiresIn=MEMBER_SESSION_EXPIRES_IN,
            user=AuthUserProfile(
                memberId=member.member_id,
                f3Name=member.f3_name,
                slackUserId=slack_user_id,
                role="member",
            ),
        )

    @classmethod
    def _find_suggested_member(cls, db: Session, display_name: str) -> MemberSummary | None:
        """Find candidate member matching display name or alias (case-insensitive)."""
        clean = display_name.strip()
        if not clean:
            return None

        # 1. Primary name exact match
        member = db.execute(
            select(Member).where(text("UPPER(F3_NAME) = :n")),
            {"n": clean.upper()},
        ).scalar_one_or_none()
        if member:
            return MemberSummary(memberId=member.member_id, f3Name=member.f3_name)

        # 2. Alias mapping exact match
        alias = db.execute(
            select(MemberAlias).where(text("UPPER(F3_ALIAS) = :a")),
            {"a": clean.upper()},
        ).scalar_one_or_none()
        if alias:
            aliased_member = db.execute(
                select(Member).where(Member.member_id == alias.member_id)
            ).scalar_one_or_none()
            if aliased_member:
                return MemberSummary(memberId=aliased_member.member_id, f3Name=aliased_member.f3_name)

        return None

    @classmethod
    def _fetch_bot_user_profile(cls, bot_token: str, user_id: str) -> dict[str, Any]:
        """Fetch full Slack user profile via users.info using bot token."""
        url = f"https://slack.com/api/users.info?user={urllib.parse.quote(user_id)}"
        req = urllib.request.Request(
            url=url,
            headers={"Authorization": f"Bearer {bot_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                res: Any = json.loads(body)
                if isinstance(res, dict) and res.get("ok"):
                    return dict(res.get("user", {}))
                return {}
        except Exception:
            return {}

    @classmethod
    def _fetch_user_info(cls, access_token: str) -> dict[str, Any]:
        """Fetch openid.connect.userInfo from Slack."""
        req = urllib.request.Request(
            url="https://slack.com/api/openid.connect.userInfo",
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                res: Any = json.loads(body)
                return dict(res) if isinstance(res, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _parse_id_token(cls, id_token: str) -> dict[str, Any]:
        """Decode unverified claims from id_token without signature verification for claims extraction."""
        if not id_token or id_token.count(".") < 2:
            return {}
        try:
            import base64

            payload_segment = id_token.split(".")[1]
            padded = payload_segment + "=" * (4 - len(payload_segment) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
            res: Any = json.loads(decoded)
            return dict(res) if isinstance(res, dict) else {}
        except Exception:
            return {}
