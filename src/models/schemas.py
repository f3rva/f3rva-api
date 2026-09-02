"""Pydantic v2 Models & Response Schemas for F3 RVA REST API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AOSummary(BaseModel):
    """Area of Operations summary."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., description="Unique AO ID")
    description: str = Field(..., description="Full display name of AO")
    slug: str | None = Field(default=None, description="URL-friendly slug")


class MemberSummary(BaseModel):
    """Member / PAX summary."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Name / Nickname")


class WorkoutResponse(BaseModel):
    """Full workout entity schema."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    workout_id: int = Field(..., alias="workoutId", serialization_alias="workoutId", description="Unique Workout ID")
    workout_date: str = Field(..., alias="workoutDate", serialization_alias="workoutDate", description="Date of workout (YYYY-MM-DD)")
    title: str = Field(..., description="Title of the workout backblast")
    author: str | None = Field(default=None, description="Author display name")
    slug: str | None = Field(default=None, description="URL-safe slug")
    backblast_url: str | None = Field(default=None, alias="backblastUrl", serialization_alias="backblastUrl", description="External backblast link")
    pax_count: int = Field(default=0, alias="paxCount", serialization_alias="paxCount", description="Total number of attendees")
    ao: list[AOSummary] = Field(default_factory=list, description="Associated AOs")
    q: list[MemberSummary] = Field(default_factory=list, description="Workout leaders / Qs")
    pax: list[MemberSummary] | None = Field(default=None, description="Full attendee list (only on detail views)")
    content: str | None = Field(default=None, description="Raw HTML backblast body content")


class MemberStatsResponse(BaseModel):
    """Member attendance statistics."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    num_workouts: int = Field(..., alias="numWorkouts", serialization_alias="numWorkouts", description="Total attended workouts")
    num_qs: int = Field(..., alias="numQs", serialization_alias="numQs", description="Total Q'd workouts")
    q_ratio: float = Field(..., alias="qRatio", serialization_alias="qRatio", description="Ratio of Qs to total workouts (0.0 to 1.0)")


class MemberDetailResponse(BaseModel):
    """Full member profile including aliases, stats, and workouts."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="Primary F3 Name")
    aliases: list[str] = Field(default_factory=list, description="Known aliases for this member")
    stats: MemberStatsResponse = Field(..., description="Member attendance statistics")
    attended_workouts: list[WorkoutResponse] = Field(default_factory=list, alias="attendedWorkouts", serialization_alias="attendedWorkouts", description="Workouts attended as PAX")
    qd_workouts: list[WorkoutResponse] = Field(default_factory=list, alias="qdWorkouts", serialization_alias="qdWorkouts", description="Workouts led as Q")


MemberProfileResponse = MemberDetailResponse


class AttendanceLeaderboardItem(BaseModel):
    """PAX attendance count entry for reports."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Name")
    num_workouts: int = Field(..., alias="numWorkouts", serialization_alias="numWorkouts", description="Total workouts attended")
    num_qs: int = Field(..., alias="numQs", serialization_alias="numQs", description="Total workouts Q'd")
    q_ratio: float = Field(..., alias="qRatio", serialization_alias="qRatio", description="Q Ratio (Qs / Workouts)")


AttendanceCount = AttendanceLeaderboardItem


class AOAttendanceSummary(BaseModel):
    """Average attendance metric for an AO."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId", description="AO ID")
    description: str = Field(..., description="AO Name / Description")
    slug: str | None = Field(default=None, description="AO slug")
    total_workouts: int = Field(..., alias="totalWorkouts", serialization_alias="totalWorkouts", description="Total workouts held")
    total_pax: int = Field(..., alias="totalPax", serialization_alias="totalPax", description="Total PAX attendees across workouts")
    average_pax: float = Field(..., alias="averagePax", serialization_alias="averagePax", description="Average PAX attendance per workout")


AOAttendanceAverage = AOAttendanceSummary


class LeaderboardEntry(BaseModel):
    """Ranked leaderboard entry for Top Q or Top PAX."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., description="Member ID")
    name: str = Field(..., description="F3 Name")
    count: int = Field(..., description="Total count (Qs or Attendances)")


AOLeaderboardEntry = LeaderboardEntry


class StreakerEntry(BaseModel):
    """Member on an active consecutive attendance streak."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Name")
    streak: int = Field(..., description="Length of active consecutive workout streak")


class AOLeaderboardResponse(BaseModel):
    """Consolidated AO detail metrics (Top Qs, Top PAX, Streakers)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId")
    description: str = Field(..., description="AO Name / Description")
    top_qs: list[LeaderboardEntry] = Field(default_factory=list, alias="topQs", serialization_alias="topQs")
    top_pax: list[LeaderboardEntry] = Field(default_factory=list, alias="topPax", serialization_alias="topPax")
    streakers: list[LeaderboardEntry] = Field(default_factory=list, description="Active attendance streakers")


class DayOfWeekAttendance(BaseModel):
    """Day of week workout aggregation."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    day_id: int = Field(..., alias="dayId", serialization_alias="dayId", description="MySQL Day of Week (1=Sunday, 7=Saturday)")
    day_name: str = Field(..., alias="dayName", serialization_alias="dayName", description="Day Name (Sunday, Monday, etc.)")
    workout_count: int = Field(..., alias="workoutCount", serialization_alias="workoutCount", description="Number of workouts held on this day")
    total_pax: int = Field(..., alias="totalPax", serialization_alias="totalPax", description="Total attendee count on this day")
    average_pax: float = Field(..., alias="averagePax", serialization_alias="averagePax", description="Average PAX per workout")


DayOfWeekStat = DayOfWeekAttendance


class MemberAODistribution(BaseModel):
    """Member attendance and Q counts grouped by AO."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId", description="AO ID")
    description: str = Field(..., description="AO Name")
    q_count: int = Field(..., alias="qCount", serialization_alias="qCount", description="Total Qs at this AO")
    pax_count: int = Field(..., alias="paxCount", serialization_alias="paxCount", description="Total PAX attendances at this AO")


MemberDistributionItem = MemberAODistribution


class MemberDistributionResponse(BaseModel):
    """Full member AO distribution breakdown."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Name")
    distribution: list[MemberAODistribution] = Field(default_factory=list, description="List of AO distribution counts")


class AOInput(BaseModel):
    """AO structure accepted in add workout request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="AO Description / Name")
    slug: str | None = Field(default=None, description="AO Slug (e.g. 'first-watch')")


class AddWorkoutRequest(BaseModel):
    """Structured payload for adding a workout."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255, description="Workout title")
    workout_date: str = Field(..., alias="workoutDate", description="Date of workout (YYYY-MM-DD)")
    qic: list[str] | str = Field(..., description="List or comma-separated string of Qs")
    pax: list[str] | str = Field(..., description="List or comma-separated string of attendees")
    aos: list[AOInput] | list[str] | str = Field(..., description="List of AOInput objects, list of AO names, or comma-separated string")
    body: str | None = Field(default=None, description="HTML or text content of the backblast")
    url: str | None = Field(default=None, description="Direct URL to original backblast post")
    author: str | None = Field(default=None, description="Author name")
    slug: str | None = Field(default=None, description="Custom URL slug")


class WorkoutCreatedResponse(BaseModel):
    """Response returned after creating a workout."""

    id: int = Field(..., description="Unique ID of the newly created workout")


class UpdateWorkoutRequest(AddWorkoutRequest):
    """Structured payload for updating/refreshing an existing workout."""

    workout_id: int | None = Field(default=None, alias="workoutId", description="Optional workout ID in payload body")


class WorkoutUpdatedResponse(BaseModel):
    """Response returned after updating a workout."""

    id: int = Field(..., description="Unique ID of the updated workout")
    message: str = Field(default="Workout updated successfully.", description="Status message")


class DeleteWorkoutResponse(BaseModel):
    """Response returned after deleting a workout."""

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., description="Confirmation message")
    workout_id: int = Field(..., alias="workoutId", serialization_alias="workoutId", description="Deleted workout ID")


class AliasClaimRequest(BaseModel):
    """Request payload to submit a member alias claim."""

    model_config = ConfigDict(populate_by_name=True)

    primary_member_id: int = Field(..., alias="primaryMemberId", description="ID of the primary/surviving member")
    alias_member_id: int = Field(..., alias="aliasMemberId", description="ID of the duplicate member record to alias and merge")


class AliasRequestResponse(BaseModel):
    """Response DTO for an alias request."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    primary_member: MemberSummary = Field(..., alias="primaryMember", serialization_alias="primaryMember")
    alias_member: MemberSummary = Field(..., alias="aliasMember", serialization_alias="aliasMember")
    status: str = Field(..., description="Request status (pending, approved, rejected)")


class AdminLoginRequest(BaseModel):
    """Admin login credentials."""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(default="admin", description="Admin username")
    password: str = Field(..., description="Admin password")


class TokenResponse(BaseModel):
    """JWT Access Token response."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken", serialization_alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType", serialization_alias="tokenType")
    expires_in: int = Field(default=86400, alias="expiresIn", serialization_alias="expiresIn")


class WorkoutScheduleItem(BaseModel):
    """Workout item for website schedule view."""

    model_config = ConfigDict(populate_by_name=True)

    location: str = Field(..., description="Location name or address")
    location_url: str = Field(..., alias="locationURL", serialization_alias="locationURL", description="Google Maps URL")
    name: str = Field(..., description="Workout / AO Name")
    tag_url: str = Field(..., alias="tagURL", serialization_alias="tagURL", description="Local archive tag URL")
    day_of_week: str = Field(..., alias="dayOfWeek", serialization_alias="dayOfWeek", description="Day of week (Monday, Tuesday, etc.)")
    start_time: str = Field(..., alias="startTime", serialization_alias="startTime", description="Start time (e.g. 0530)")
    end_time: str = Field(..., alias="endTime", serialization_alias="endTime", description="End time (e.g. 0615)")
    workout_style: str = Field(..., alias="workoutStyle", serialization_alias="workoutStyle", description="Workout style / category (Bootcamp, Run, etc.)")
    site_q: str = Field(..., alias="siteQ", serialization_alias="siteQ", description="Site Q leader name")
    notes: str = Field(..., description="Notes and instructions")


class WorkoutScheduleResponse(BaseModel):
    """Top-level schedule response matching f3rva-website expectations."""

    model_config = ConfigDict(populate_by_name=True)

    first_f: list[WorkoutScheduleItem] = Field(..., alias="1stF", serialization_alias="1stF", description="List of 1stF workouts")


class ErrorResponse(BaseModel):
    """Standard error response matching legacy JSON structure."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    error_code: int = Field(..., alias="errorCode", serialization_alias="errorCode")
    error_message: str = Field(..., alias="errorMessage", serialization_alias="errorMessage")


class SlackAuthRequest(BaseModel):
    """Request payload for exchanging Slack OAuth code."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str = Field(..., description="Authorization code from Slack OAuth redirect")
    redirect_uri: str = Field(..., alias="redirectUri", description="OAuth redirect URI used in initiation")


class SlackUserProfile(BaseModel):
    """Slack User profile extracted during OAuth."""

    model_config = ConfigDict(populate_by_name=True)

    slack_user_id: str = Field(..., alias="slackUserId", serialization_alias="slackUserId")
    slack_team_id: str = Field(..., alias="slackTeamId", serialization_alias="slackTeamId")
    display_name: str = Field(..., alias="displayName", serialization_alias="displayName")
    real_name: str | None = Field(default=None, alias="realName", serialization_alias="realName")
    email: str | None = Field(default=None)


class AuthUserProfile(BaseModel):
    """Authenticated user profile returned upon successful login."""

    model_config = ConfigDict(populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name")
    slack_user_id: str = Field(..., alias="slackUserId", serialization_alias="slackUserId")
    role: str = Field(default="member", description="User role: member or admin")


class SlackAuthResponse(BaseModel):
    """Response returned from Slack OAuth handshake."""

    model_config = ConfigDict(populate_by_name=True)

    is_linked: bool = Field(..., alias="isLinked", serialization_alias="isLinked", description="True if Slack user is linked to an F3 member")
    access_token: str | None = Field(default=None, alias="accessToken", serialization_alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType", serialization_alias="tokenType")
    expires_in: int | None = Field(default=None, alias="expiresIn", serialization_alias="expiresIn")
    user: AuthUserProfile | None = Field(default=None, description="User profile if authenticated")
    suggested_member: MemberSummary | None = Field(default=None, alias="suggestedMember", serialization_alias="suggestedMember")
    slack_user: SlackUserProfile | None = Field(default=None, alias="slackUser", serialization_alias="slackUser")
    temp_token: str | None = Field(default=None, alias="tempToken", serialization_alias="tempToken")


class SlackConfirmLinkRequest(BaseModel):
    """Request payload to confirm linking a Slack user to an F3 member profile."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    temp_token: str = Field(..., alias="tempToken", description="Temporary signed token from initial Slack handshake")
    member_id: int = Field(..., alias="memberId", description="Selected F3 Member ID to link")
