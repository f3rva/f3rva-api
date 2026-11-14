"""Admin Operations & Protected Management REST API Router."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.schemas import (
    AliasClaimRequest,
    AliasRequestResponse,
    ErrorResponse,
    GrantMemberRoleRequest,
    MemberRoleAssignmentResponse,
    RevokeMemberRoleResponse,
)
from src.services.alias_service import AliasService
from src.services.role_service import RoleService
from src.utils.security import get_current_admin

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[dict[str, Any], Depends(get_current_admin)]


@router.get(
    "/aliases/requests",
    response_model=list[AliasRequestResponse],
    summary="Get pending alias requests (Admin)",
    description="Retrieves all pending member alias requests awaiting administrator approval (Requires Admin Bearer Token).",
    responses={
        200: {"description": "List of pending alias requests."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
    },
)
def get_pending_alias_requests(
    db: DbSession,
    current_admin: CurrentAdmin,
) -> list[AliasRequestResponse]:
    """Retrieve all pending alias requests."""
    return AliasService.get_pending_requests(db=db)


@router.post(
    "/aliases/approve/{primary_member_id}/{alias_member_id}",
    response_model=AliasRequestResponse,
    summary="Approve alias request (Admin)",
    description="Approves a member alias request, merges attendance records, updates aliases, and removes the duplicate member (Requires Admin Bearer Token).",
    responses={
        200: {"description": "Alias approved and records merged successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
        404: {"model": ErrorResponse, "description": "Alias request not found."},
    },
)
def approve_alias_request(
    db: DbSession,
    primary_member_id: int,
    alias_member_id: int,
    current_admin: CurrentAdmin,
) -> AliasRequestResponse:
    """Approve alias request and merge records."""
    return AliasService.approve_alias(
        db=db, primary_id=primary_member_id, alias_id=alias_member_id
    )


@router.post(
    "/aliases/reject/{primary_member_id}/{alias_member_id}",
    response_model=AliasRequestResponse,
    summary="Reject alias request (Admin)",
    description="Rejects a pending member alias request (Requires Admin Bearer Token).",
    responses={
        200: {"description": "Alias request rejected successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
        404: {"model": ErrorResponse, "description": "Alias request not found."},
    },
)
def reject_alias_request(
    db: DbSession,
    primary_member_id: int,
    alias_member_id: int,
    current_admin: CurrentAdmin,
) -> AliasRequestResponse:
    """Reject a pending alias request."""
    return AliasService.reject_alias(
        db=db, primary_id=primary_member_id, alias_id=alias_member_id
    )


@router.post(
    "/members/merge",
    response_model=AliasRequestResponse,
    summary="Directly merge two members (Admin)",
    description="Directly merges a duplicate member record into a primary member, creates audit trails, updates aliases, and reassigns attendance (Requires Admin Bearer Token).",
    responses={
        200: {"description": "Members merged successfully."},
        400: {"model": ErrorResponse, "description": "Cannot merge identical members."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
        404: {"model": ErrorResponse, "description": "One or more members not found."},
    },
)
def direct_merge_members(
    db: DbSession,
    payload: AliasClaimRequest,
    current_admin: CurrentAdmin,
) -> AliasRequestResponse:
    """Directly merge two member entities."""
    return AliasService.direct_merge(
        db=db,
        primary_id=payload.primary_member_id,
        alias_id=payload.alias_member_id,
    )


@router.get(
    "/roles",
    response_model=list[MemberRoleAssignmentResponse],
    summary="Get all member role assignments (Admin)",
    description="Retrieves all active role assignments from MEMBER_ROLE (Requires Admin Bearer Token).",
    responses={
        200: {"description": "List of member role assignments."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
    },
)
def get_role_assignments(
    db: DbSession,
    current_admin: CurrentAdmin,
) -> list[MemberRoleAssignmentResponse]:
    """Retrieve all assigned member roles."""
    return RoleService.get_role_assignments(db=db)


@router.post(
    "/members/{member_id}/roles",
    response_model=MemberRoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant role to member (Admin)",
    description="Assigns an access control role (e.g., 'admin') to the specified member (Requires Admin Bearer Token).",
    responses={
        201: {"description": "Role granted successfully."},
        400: {"model": ErrorResponse, "description": "Invalid role specified."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
        404: {"model": ErrorResponse, "description": "Member not found."},
    },
)
def grant_member_role(
    db: DbSession,
    member_id: int,
    payload: GrantMemberRoleRequest,
    current_admin: CurrentAdmin,
) -> MemberRoleAssignmentResponse:
    """Grant a role to a member."""
    acting_member_id = current_admin.get("member_id")
    return RoleService.grant_role(
        db=db,
        member_id=member_id,
        role=payload.role,
        granted_by_member_id=int(acting_member_id) if acting_member_id is not None else None,
    )


@router.delete(
    "/members/{member_id}/roles/{role}",
    response_model=RevokeMemberRoleResponse,
    summary="Revoke role from member (Admin)",
    description="Revokes an access control role from the specified member (Requires Admin Bearer Token).",
    responses={
        200: {"description": "Role revoked successfully."},
        400: {"model": ErrorResponse, "description": "Cannot revoke own admin role."},
        401: {"model": ErrorResponse, "description": "Missing or invalid authorization token."},
        403: {"model": ErrorResponse, "description": "Admin role required."},
        404: {"model": ErrorResponse, "description": "Role assignment not found."},
    },
)
def revoke_member_role(
    db: DbSession,
    member_id: int,
    role: str,
    current_admin: CurrentAdmin,
) -> RevokeMemberRoleResponse:
    """Revoke a role from a member."""
    acting_member_id = current_admin.get("member_id")
    return RoleService.revoke_role(
        db=db,
        member_id=member_id,
        role=role,
        acting_member_id=int(acting_member_id) if acting_member_id is not None else None,
    )
