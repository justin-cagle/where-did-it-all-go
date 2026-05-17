"""SQLAlchemy models for the households domain.

Tables:
  households_household      — top-level organizational unit
  households_user           — application user (cross-household identity)
  households_membership     — links a user to a household with a role
  households_refresh_token  — server-side refresh token records (idle-timeout)
"""

import hashlib
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.households.enums import HouseholdRole, VisibilityMode
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.ids import new_uuid
from app.platform.time import utcnow


class Household(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Top-level organizational unit. All financial data is household-scoped."""

    __tablename__ = "households_household"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    visibility_mode: Mapped[str] = mapped_column(
        sa.Enum(VisibilityMode, name="visibility_mode", native_enum=False, length=40),
        nullable=False,
        default=VisibilityMode.FULLY_SHARED,
    )
    home_currency: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    memberships: Mapped[list["HouseholdMembership"]] = relationship(
        "HouseholdMembership",
        back_populates="household",
        lazy="select",
    )

    __table_args__ = (sa.Index("ix_households_household_name", "name"),)

    def __repr__(self) -> str:
        return f"Household(id={self.id}, name={self.name!r})"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Application user. Identity is cross-household; memberships link to households."""

    __tablename__ = "households_user"

    email: Mapped[str] = mapped_column(
        sa.String(320),
        nullable=False,
        unique=True,
        comment="Stored lowercase; used as the login identifier",
    )
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_app_admin: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        comment="App Admin: manages OIDC config, encryption keys, invites (not financial role)",
    )

    # Local auth fields — None when user authenticates via OIDC only.
    # totp_secret: stored plaintext for now. TODO: encrypt with master key
    # when field-level encryption layer is implemented (security.md).
    password_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Base32 TOTP secret; TODO encrypt at rest (security.md)",
    )
    totp_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    memberships: Mapped[list["HouseholdMembership"]] = relationship(
        "HouseholdMembership",
        back_populates="user",
        lazy="select",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        lazy="select",
    )

    __table_args__ = (sa.Index("ix_households_user_email", "email", unique=True),)

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"


class HouseholdMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Links a user to a household with a financial role."""

    __tablename__ = "households_membership"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        sa.Enum(HouseholdRole, name="household_role", native_enum=False, length=16),
        nullable=False,
        default=HouseholdRole.MEMBER,
    )

    household: Mapped[Household] = relationship(
        "Household", back_populates="memberships", lazy="select"
    )
    user: Mapped[User] = relationship("User", back_populates="memberships", lazy="select")

    __table_args__ = (
        # A user can have at most one active membership per household.
        sa.UniqueConstraint(
            "household_id",
            "user_id",
            name="uq_households_membership_hh_user",
        ),
        sa.Index("ix_households_membership_household", "household_id"),
        sa.Index("ix_households_membership_user", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"HouseholdMembership(household={self.household_id}, "
            f"user={self.user_id}, role={self.role!r})"
        )


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """Server-side refresh token record.

    The raw token (UUID4) is sent to the client as an httpOnly cookie.
    Only a SHA-256 hash is stored in the DB — the raw token is never persisted.

    Idle timeout: if now() > last_used_at + idle_timeout_seconds, the token
    is considered expired (regardless of expires_at).

    Token rotation: each successful refresh revokes the old token and issues
    a new one. Re-use of a revoked token signals potential token theft and
    should trigger full session invalidation.
    """

    __tablename__ = "households_refresh_token"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=True,
        comment="The household context this refresh token is scoped to",
    )
    token_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the raw opaque token (UUID4)",
    )
    issued_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_used_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        comment="Absolute expiry — independent of idle timeout",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    idle_timeout_seconds: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1800,
        comment="Sliding window idle timeout in seconds (default: 30 min)",
    )
    user_agent: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="User-Agent header from the session that issued this token",
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens", lazy="select")

    __table_args__ = (
        sa.Index("ix_households_refresh_token_user", "user_id"),
        sa.Index("ix_households_refresh_token_hash", "token_hash", unique=True),
    )

    def __repr__(self) -> str:
        return f"RefreshToken(user={self.user_id}, expires={self.expires_at})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """SHA-256 hex digest of the raw opaque token."""
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def generate_raw() -> str:
        """Generate a cryptographically random opaque token string."""
        return str(new_uuid()) + str(uuid.uuid4())
