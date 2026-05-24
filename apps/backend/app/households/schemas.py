"""Pydantic v2 request/response schemas for the households module.

All schemas use strict validation. No floats. UUIDs are passed as str in
JSON (UUID serialization) but parsed back to uuid.UUID internally.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.households.enums import HouseholdRole, InvitationStatus, VisibilityMode


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Register a new user with local auth credentials."""

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    """Local auth login."""

    email: EmailStr
    password: str
    totp_code: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class StepUpRequest(BaseModel):
    """Step-up authentication — re-enter password or provide TOTP."""

    password: str | None = None
    totp_code: str | None = None


class TokenResponse(BaseModel):
    """Response body for auth endpoints (tokens are in httpOnly cookies)."""

    user_id: uuid.UUID
    is_app_admin: bool
    message: str = "authenticated"


class RegisterResponse(TokenResponse):
    """Response body for POST /auth/register.

    Extends TokenResponse with post-registration routing hints.
    """

    has_household: bool = False
    redirect: str = "/onboarding"


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


class UserOut(_Base):
    """User info returned in responses."""

    id: uuid.UUID
    email: str
    display_name: str
    is_app_admin: bool
    totp_enabled: bool
    avatar_url: str | None
    created_at: datetime


class TotpSetupOut(BaseModel):
    """TOTP enrollment response."""

    provisioning_uri: str
    secret: str


class SessionOut(_Base):
    """Active refresh token (session) info returned in responses."""

    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime
    user_agent: str | None


class ChangePasswordRequest(BaseModel):
    """Change the current user's local auth password."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    """Update mutable fields on the authenticated user's profile."""

    display_name: str = Field(min_length=1, max_length=255)
    avatar_url: str | None = None


# ---------------------------------------------------------------------------
# Household schemas
# ---------------------------------------------------------------------------


class HouseholdCreate(BaseModel):
    """Create a new household."""

    name: str = Field(min_length=1, max_length=255)
    visibility_mode: VisibilityMode = VisibilityMode.FULLY_SHARED
    home_currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("home_currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class HouseholdUpdate(BaseModel):
    """Mutable household fields."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    visibility_mode: VisibilityMode | None = None
    home_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("home_currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class HouseholdOut(_Base):
    """Household info returned in responses."""

    id: uuid.UUID
    name: str
    visibility_mode: str
    home_currency: str
    created_at: datetime


class HouseholdUpdateOut(HouseholdOut):
    """Household info returned after a PATCH update.

    recompute_started=True when home_currency changed and the FX recompute
    job was successfully enqueued. Clients should show a recalculating banner
    until the fx_recompute_complete SSE event is received.
    """

    recompute_started: bool = False


# ---------------------------------------------------------------------------
# Membership schemas
# ---------------------------------------------------------------------------


class AddMemberRequest(BaseModel):
    """Add an existing user to a household (requires step-up auth)."""

    email: EmailStr
    role: HouseholdRole = HouseholdRole.MEMBER

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class MembershipOut(_Base):
    """Membership record returned in responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    user: UserOut


# ---------------------------------------------------------------------------
# Invitation schemas
# ---------------------------------------------------------------------------


class CreateInvitationRequest(BaseModel):
    """Create a household invitation."""

    email: EmailStr
    role: HouseholdRole = HouseholdRole.MEMBER

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class InvitationOut(_Base):
    """Invitation info returned to household owners."""

    id: uuid.UUID
    household_id: uuid.UUID
    household_name: str
    invited_email: str
    invited_by_name: str
    role: str
    status: str
    expires_at: datetime
    email_sent: bool
    created_at: datetime
    invite_url: str

    @classmethod
    def from_invite(cls, invite: object, invite_url: str) -> "InvitationOut":
        from app.households.models import HouseholdInvitation

        inv: HouseholdInvitation = invite  # type: ignore[assignment]
        hh_name = inv.household.name if inv.household else ""
        by_name = inv.invited_by.display_name if inv.invited_by else ""
        return cls(
            id=inv.id,
            household_id=inv.household_id,
            household_name=hh_name,
            invited_email=inv.invited_email,
            invited_by_name=by_name,
            role=inv.role,
            status=inv.status,
            expires_at=inv.expires_at,
            email_sent=inv.email_sent,
            created_at=inv.created_at,
            invite_url=invite_url,
        )


class InviteMetadataOut(BaseModel):
    """Public metadata for the accept page (token never exposed)."""

    household_name: str
    invited_by_name: str
    invited_email: str
    status: str
    expires_at: datetime

    @classmethod
    def from_invite(cls, invite: object) -> "InviteMetadataOut":
        from app.households.models import HouseholdInvitation

        inv: HouseholdInvitation = invite  # type: ignore[assignment]
        hh_name = inv.household.name if inv.household else ""
        by_name = inv.invited_by.display_name if inv.invited_by else ""
        return cls(
            household_name=hh_name,
            invited_by_name=by_name,
            invited_email=inv.invited_email,
            status=inv.status,
            expires_at=inv.expires_at,
        )


class AcceptInviteResponse(BaseModel):
    """Response to a successful invitation accept."""

    household_id: uuid.UUID
    membership_id: uuid.UUID


class SmtpStatusResponse(BaseModel):
    """SMTP configuration status (non-sensitive bool)."""

    smtp_configured: bool


class InvitationStatusFilter(BaseModel):
    """Filter for listing invitations."""

    status: InvitationStatus | None = None
