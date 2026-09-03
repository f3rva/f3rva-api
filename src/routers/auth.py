"""Slack OAuth & User Authentication REST API Router."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import (
    AuthUserProfile,
    ErrorResponse,
    SlackAuthRequest,
    SlackAuthResponse,
    SlackConfirmLinkRequest,
)
from src.models.workout import Member
from src.services.slack_auth_service import SlackAuthService
from src.utils.security import get_current_user

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/slack",
    response_model=SlackAuthResponse,
    summary="Slack OAuth code exchange and login",
    description="Exchanges an authorization code with Slack, verifies workspace identity, and either returns a JWT session or a link confirmation prompt.",
    responses={
        200: {"description": "Slack identity resolved successfully."},
        400: {"model": ErrorResponse, "description": "Invalid OAuth code or incomplete identity."},
        403: {"model": ErrorResponse, "description": "Unauthorized Slack workspace."},
    },
)
def slack_login(
    db: DbSession,
    payload: SlackAuthRequest,
) -> SlackAuthResponse:
    """Handle Slack OAuth authorization code exchange and member login."""
    slack_user = SlackAuthService.exchange_code(code=payload.code, redirect_uri=payload.redirect_uri)
    return SlackAuthService.handle_slack_login(db=db, slack_user=slack_user)


@router.post(
    "/slack/confirm-link",
    response_model=SlackAuthResponse,
    summary="Confirm linking Slack identity to F3 Member",
    description="Persists confirmed association between Slack user and chosen F3 Member profile, then issues a signed JWT session.",
    responses={
        200: {"description": "Profile linked successfully and session token issued."},
        400: {"model": ErrorResponse, "description": "Invalid or expired temporary link token."},
        404: {"model": ErrorResponse, "description": "Selected Member ID not found."},
    },
)
def confirm_slack_link(
    db: DbSession,
    payload: SlackConfirmLinkRequest,
) -> SlackAuthResponse:
    """Confirm and persist member link to MEMBER_SLACK table."""
    return SlackAuthService.confirm_member_link(
        db=db, temp_token=payload.temp_token, member_id=payload.member_id
    )


@router.get(
    "/me",
    response_model=AuthUserProfile,
    summary="Get current authenticated user session",
    description="Retrieves the authenticated user profile and roles from the active Bearer JWT token.",
    responses={
        200: {"description": "Active user profile found."},
        401: {"model": ErrorResponse, "description": "Missing or expired Bearer token."},
    },
)
def get_current_user_profile(
    db: DbSession,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> AuthUserProfile:
    """Retrieve profile and roles for the current authenticated user session."""
    role = current_user.get("role", "member")
    member_id = current_user.get("member_id")

    if role == "admin" and not member_id:
        return AuthUserProfile(
            memberId=0,
            f3Name=str(current_user.get("sub", "admin")),
            slackUserId="",
            role="admin",
        )

    if not member_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": 4010, "errorMessage": "Invalid session profile."},
        )

    member = db.execute(
        select(Member).where(Member.member_id == int(member_id))
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": 2001, "errorMessage": f"Member with ID {member_id} not found."},
        )

    return AuthUserProfile(
        memberId=member.member_id,
        f3Name=member.f3_name,
        slackUserId=str(current_user.get("sub", "")),
        role=role,
    )
