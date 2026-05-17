"""Pydantic v2 request/response schemas for the households module.

All schemas use strict validation. No floats. UUIDs are passed as str in
JSON (UUID serialization) but parsed back to uuid.UUID internally.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.households.enums import HouseholdRole, VisibilityMode


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
    created_at: datetime


class TotpSetupOut(BaseModel):
    """TOTP enrollment response."""

    provisioning_uri: str


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
