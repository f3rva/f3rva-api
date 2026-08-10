"""Pydantic v2 Request and Response Data Transfer Objects (DTOs)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AOSummary(BaseModel):
    """Area of Operations summary DTO."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)

    id: int | None = Field(default=None, description="AO Identifier")
    description: str = Field(..., description="AO Description / Name")
    slug: str | None = Field(default=None, description="AO URL slug")


class MemberSummary(BaseModel):
    """Member summary DTO representing a Q or PAX attendee."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Nickname / Name")


class WorkoutResponse(BaseModel):
    """Workout response model matching legacy PHP JSON contract 1:1."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)

    workout_id: int = Field(..., alias="workoutId", serialization_alias="workoutId", description="Unique Workout ID")
    backblast_url: str | None = Field(default=None, alias="backblastUrl", serialization_alias="backblastUrl")
    title: str = Field(..., description="Backblast Title")
    author: str | None = Field(default=None, description="Author")
    slug: str | None = Field(default=None, description="Backblast URL slug")
    ao: list[AOSummary] = Field(default_factory=list, description="Associated AOs")
    q: list[MemberSummary] = Field(default_factory=list, description="Workout Leaders (Qs)")
    pax: list[MemberSummary] | None = Field(default=None, description="Workout attendees (PAX roster)")
    pax_count: int = Field(default=0, alias="paxCount", serialization_alias="paxCount", description="Attendee count")
    workout_date: str = Field(..., alias="workoutDate", serialization_alias="workoutDate", description="Workout Date YYYY-MM-DD")
    content: str | None = Field(default=None, description="Backblast HTML Content")


class MemberStatsResponse(BaseModel):
    """Member statistical summary representing workout attendance and Q ratios."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    num_workouts: int = Field(..., alias="numWorkouts", serialization_alias="numWorkouts", description="Total workouts attended")
    num_qs: int = Field(..., alias="numQs", serialization_alias="numQs", description="Total workouts led (Q'd)")
    q_ratio: float = Field(..., alias="qRatio", serialization_alias="qRatio", description="Ratio of Qs to total workouts (0.0 to 1.0)")


class MemberDetailResponse(BaseModel):
    """Comprehensive member profile including aliases, stats, and workout histories."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Unique Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="Primary F3 Name")
    aliases: list[str] = Field(default_factory=list, description="Registered aliases for this member")
    stats: MemberStatsResponse | None = Field(default=None, description="Workout attendance and Q stats")
    attended_workouts: list[WorkoutResponse] = Field(default_factory=list, alias="attendedWorkouts", serialization_alias="attendedWorkouts", description="Workouts attended as PAX")
    qd_workouts: list[WorkoutResponse] = Field(default_factory=list, alias="qdWorkouts", serialization_alias="qdWorkouts", description="Workouts led as Q")


class AttendanceLeaderboardItem(BaseModel):
    """Leaderboard item for member attendance over a given date range."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="F3 Nickname")
    num_workouts: int = Field(..., alias="numWorkouts", serialization_alias="numWorkouts", description="Workouts attended in period")
    num_qs: int = Field(..., alias="numQs", serialization_alias="numQs", description="Workouts led (Q'd) in period")
    q_ratio: float = Field(..., alias="qRatio", serialization_alias="qRatio", description="Q to workout ratio in period")


class AOAttendanceSummary(BaseModel):
    """Statistical summary of workout attendance across an Area of Operations (AO)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId", description="AO ID")
    description: str = Field(..., description="AO Name / Description")
    slug: str | None = Field(default=None, description="AO URL slug")
    total_workouts: int = Field(..., alias="totalWorkouts", serialization_alias="totalWorkouts", description="Total workouts conducted")
    total_pax: int = Field(..., alias="totalPax", serialization_alias="totalPax", description="Total PAX attendance sum")
    average_pax: float = Field(..., alias="averagePax", serialization_alias="averagePax", description="Average PAX per workout")


class LeaderboardEntry(BaseModel):
    """Generic leaderboard entry for top Qs, top attendees, and streakers."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., description="Entity identifier (Member ID or AO ID)")
    name: str = Field(..., description="Entity display name")
    count: int = Field(..., description="Count or streak value")


class AOLeaderboardResponse(BaseModel):
    """Leaderboard analytics for a specific AO including top leaders, top PAX, and active streaks."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId", description="AO ID")
    description: str = Field(..., description="AO Description")
    top_qs: list[LeaderboardEntry] = Field(default_factory=list, alias="topQs", serialization_alias="topQs", description="Top Q leaders at this AO")
    top_pax: list[LeaderboardEntry] = Field(default_factory=list, alias="topPax", serialization_alias="topPax", description="Top PAX attendees at this AO")
    streakers: list[LeaderboardEntry] = Field(default_factory=list, description="Members with consecutive workout attendance streaks")


class DayOfWeekAttendance(BaseModel):
    """Attendance statistics grouped by day of the week."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    day_id: int = Field(..., alias="dayId", serialization_alias="dayId", description="Day Index (1=Sunday, 7=Saturday)")
    day_name: str = Field(..., alias="dayName", serialization_alias="dayName", description="Day Name (e.g. Monday)")
    workout_count: int = Field(..., alias="workoutCount", serialization_alias="workoutCount", description="Workouts hosted on this day")
    total_pax: int = Field(..., alias="totalPax", serialization_alias="totalPax", description="Sum of PAX attendance on this day")
    average_pax: float = Field(..., alias="averagePax", serialization_alias="averagePax", description="Average PAX per workout")


class MemberAODistribution(BaseModel):
    """Breakdown of workouts attended and Q'd by AO for a specific member."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ao_id: int = Field(..., alias="aoId", serialization_alias="aoId", description="AO ID")
    description: str = Field(..., description="AO Name")
    q_count: int = Field(..., alias="qCount", serialization_alias="qCount", description="Workouts Q'd at this AO")
    pax_count: int = Field(..., alias="paxCount", serialization_alias="paxCount", description="Workouts attended at this AO")


class MemberDistributionResponse(BaseModel):
    """Member AO attendance distribution response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    member_id: int = Field(..., alias="memberId", serialization_alias="memberId", description="Member ID")
    f3_name: str = Field(..., alias="f3Name", serialization_alias="f3Name", description="Member Name")
    distribution: list[MemberAODistribution] = Field(default_factory=list, description="AO attendance breakdown")


# ==========================================
# Phase 5: Mutation & Admin Schemas
# ==========================================


class AOInput(BaseModel):
    """Area of Operations input specification."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    name: str = Field(..., min_length=1, description="AO description/name (e.g. 'First Watch')")
    slug: str | None = Field(None, description="AO URL slug (e.g. 'first-watch')")


class AddWorkoutRequest(BaseModel):
    """Structured payload to add a workout directly with data."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    title: str = Field(..., min_length=1, description="Workout title")
    workout_date: str = Field(..., alias="workoutDate", description="Workout date (YYYY-MM-DD, YYYYMMDD, or MM/DD/YYYY)")
    qic: str | list[str] = Field(..., description="Workout leader(s) (Qs) as comma-separated string or list of names")
    pax: str | list[str] = Field(..., description="Workout attendees (PAX) as comma-separated string or list of names")
    aos: list[AOInput] = Field(..., min_length=1, description="AOs where workout was hosted (list of objects with 'name' and optional 'slug')")
    url: str | None = Field(None, description="Backblast URL")
    author: str | None = Field(None, description="Backblast author")
    slug: str | None = Field(None, description="URL slug")
    body: str | None = Field(None, description="HTML or plain text backblast body")


class WorkoutCreatedResponse(BaseModel):
    """Response returned after creating a workout."""

    id: int = Field(..., description="Unique ID of the newly created workout")


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


class ErrorResponse(BaseModel):
    """Standard error response matching legacy PHP JSON structure."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    error_code: int = Field(..., alias="errorCode", serialization_alias="errorCode")
    error_message: str = Field(..., alias="errorMessage", serialization_alias="errorMessage")
