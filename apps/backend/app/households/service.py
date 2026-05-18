"""Household service layer — all business logic for households and auth.

No database joins across module boundaries. All cross-module
communication goes through published interfaces (see architecture.md).

This module may import from app.security (for JWT, password, TOTP) and
app.audit (for audit logging), but never from other domain modules.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.households import models
from app.households.enums import HouseholdRole, VisibilityMode
from app.households.models import Household, HouseholdMembership, RefreshToken, User
from app.platform import events as platform_events
from app.security import hooks as auth_hooks
from app.security import jwt as jwt_service
from app.security import password as pwd_service
from app.security import totp as totp_service

_REFRESH_TOKEN_TTL = timedelta(days=30)
_DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes
# Pre-computed once at startup for constant-time guard on unknown-user auth paths
_DUMMY_HASH: str = pwd_service.hash_password("dummy")


class AuthenticationError(Exception):
    """Raised when credentials are invalid or session is expired."""


class NotFoundError(Exception):
    """Raised when a requested entity does not exist or is not visible."""


class PermissionError(Exception):
    """Raised when the actor lacks the required role or step-up auth."""


class ConflictError(Exception):
    """Raised when an operation would violate a uniqueness constraint."""


class RegistrationClosedError(Exception):
    """Raised when ALLOW_REGISTRATION=False and no valid invite is present."""


class RegistrationLimitReachedError(Exception):
    """Raised when active user count >= REGISTRATION_LIMIT and no invite is present."""


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str,
    invite_token: str | None = None,
) -> User:
    """Register a new user, enforcing instance registration controls.

    Invited users (invite_token is not None) bypass all checks.
    Raises RegistrationClosedError or RegistrationLimitReachedError when blocked.
    """
    if invite_token is None:
        from app.config import get_settings

        allow_reg, reg_limit = await _get_effective_registration_settings(session, get_settings())
        if not allow_reg:
            raise RegistrationClosedError("registration is closed")
        if reg_limit is not None:
            active = await _count_active_users(session)
            if active >= reg_limit:
                raise RegistrationLimitReachedError("registration limit reached")

    return await create_user(
        session,
        email=email,
        display_name=display_name,
        password=password,
    )


async def _count_active_users(session: AsyncSession) -> int:
    result = await session.execute(
        sa.select(sa.func.count()).select_from(User).where(User.archived_at.is_(None))
    )
    return result.scalar_one()


async def _get_effective_registration_settings(
    session: AsyncSession,
    settings: "Settings",
) -> tuple[bool, int | None]:
    """Return (allow_registration, registration_limit) merging env + DB overrides.

    Uses raw SQL to read admin_setting — avoids importing the admin module.
    DB values take precedence over env vars.
    """
    result = await session.execute(
        sa.text(
            "SELECT key, value FROM admin_setting "
            "WHERE key IN ('allow_registration', 'registration_limit')"
        )
    )
    overrides = {row[0]: row[1] for row in result.fetchall()}

    allow_reg: bool = settings.allow_registration
    if "allow_registration" in overrides:
        allow_reg = overrides["allow_registration"].lower() == "true"

    reg_limit: int | None = settings.registration_limit
    if "registration_limit" in overrides:
        v = overrides["registration_limit"]
        reg_limit = None if v == "null" else int(v)

    return allow_reg, reg_limit


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str,
    is_app_admin: bool = False,
) -> User:
    """Register a new user with local auth credentials."""
    existing = await _get_user_by_email(session, email)
    if existing is not None:
        raise ConflictError(f"email already registered: {email}")

    user = User(
        email=email.lower(),
        display_name=display_name,
        is_app_admin=is_app_admin,
        password_hash=pwd_service.hash_password(password),
    )
    session.add(user)
    await session.flush()  # populate id

    await _write_audit(
        session,
        actor_type=ActorType.SYSTEM,
        actor_id=None,
        household_id=None,
        entity_type="user",
        entity_id=user.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/id", "value": str(user.id)}],
    )
    return user


async def authenticate_local(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    totp_code: str | None,
) -> User:
    """Verify credentials and return the authenticated User.

    Raises AuthenticationError on any failure (intentionally opaque
    to prevent user-enumeration).
    """
    user = await _get_user_by_email(session, email)
    if user is None or user.password_hash is None:
        # Constant-time dummy verify to prevent user-enumeration via timing
        pwd_service.verify_password(password, _DUMMY_HASH)
        raise AuthenticationError("invalid credentials")

    pm = auth_hooks.get_plugin_manager()
    # firstresult=True → pluggy returns the first non-None result directly, not a list
    result: bool | None = pm.hook.authenticate_local(
        username=email,
        password=password,
        stored_hash=user.password_hash,
        totp_code=totp_code,
        totp_secret=user.totp_secret,
        totp_enabled=user.totp_enabled,
    )
    if not result:
        raise AuthenticationError("invalid credentials")

    # Rehash if argon2 parameters changed
    if user.password_hash and pwd_service.needs_rehash(user.password_hash):
        user.password_hash = pwd_service.hash_password(password)

    return user


# ---------------------------------------------------------------------------
# Token issuance and refresh
# ---------------------------------------------------------------------------


async def issue_tokens(
    session: AsyncSession,
    *,
    user: User,
    household_id: uuid.UUID | None,
    jwt_secret: str,
    idle_timeout_seconds: int = _DEFAULT_IDLE_TIMEOUT,
) -> tuple[str, str]:
    """Issue a JWT access token + opaque refresh token for a session.

    Returns (access_token_str, refresh_token_raw).
    The caller must set both as httpOnly cookies.
    """
    access_token = jwt_service.issue_access_token(
        user_id=user.id,
        household_id=household_id,
        is_app_admin=user.is_app_admin,
        secret=jwt_secret,
    )

    raw_token = RefreshToken.generate_raw()
    now = datetime.now(tz=UTC)
    rt = RefreshToken(
        user_id=user.id,
        household_id=household_id,
        token_hash=RefreshToken.hash_token(raw_token),
        issued_at=now,
        last_used_at=now,
        expires_at=now + _REFRESH_TOKEN_TTL,
        idle_timeout_seconds=idle_timeout_seconds,
    )
    session.add(rt)
    await session.flush()

    return access_token, raw_token


async def refresh_tokens(
    session: AsyncSession,
    *,
    raw_refresh_token: str,
    jwt_secret: str,
) -> tuple[str, str]:
    """Rotate the refresh token (sliding-window idle timeout).

    Returns (new_access_token, new_refresh_token_raw).
    Raises AuthenticationError if the token is invalid, expired, or revoked.
    """
    token_hash = RefreshToken.hash_token(raw_refresh_token)
    rt = await _get_refresh_token_by_hash(session, token_hash)

    if rt is None:
        raise AuthenticationError("refresh token not found")
    if rt.revoked_at is not None:
        raise AuthenticationError("refresh token has been revoked")

    now = datetime.now(tz=UTC)
    if now > rt.expires_at:
        raise AuthenticationError("refresh token expired")

    idle_deadline = rt.last_used_at + timedelta(seconds=rt.idle_timeout_seconds)
    if now > idle_deadline:
        await _revoke_refresh_token(session, rt)
        raise AuthenticationError("session idle timeout")

    # Load user for the new token
    user = await _get_user_by_id(session, rt.user_id)
    if user is None:
        raise AuthenticationError("user not found")

    # Revoke old token (rotation — prevents replay of stolen tokens)
    await _revoke_refresh_token(session, rt)

    # Issue new tokens
    new_access, new_raw = await issue_tokens(
        session,
        user=user,
        household_id=rt.household_id,
        jwt_secret=jwt_secret,
        idle_timeout_seconds=rt.idle_timeout_seconds,
    )
    return new_access, new_raw


async def revoke_all_tokens(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Revoke all refresh tokens for a user (logout from all devices)."""
    now = datetime.now(tz=UTC)
    stmt = (
        sa.update(models.RefreshToken)
        .where(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.execute(stmt)


async def step_up_auth(
    session: AsyncSession,
    *,
    user: User,
    password: str | None,
    totp_code: str | None,
    jwt_secret: str,
) -> str:
    """Validate step-up credentials and return a new access token with step_up_until.

    Raises AuthenticationError if credentials are insufficient.
    """
    if user.password_hash is None:
        raise AuthenticationError("no local auth configured for this user")

    # Require either password or TOTP (but TOTP alone is not enough without a password set)
    if password is not None:
        if not pwd_service.verify_password(password, user.password_hash):
            raise AuthenticationError("invalid credentials")
    elif totp_code is not None and user.totp_enabled and user.totp_secret:
        if not totp_service.verify_code(user.totp_secret, totp_code):
            raise AuthenticationError("invalid TOTP code")
    else:
        raise AuthenticationError("step-up requires password or TOTP")

    # Look up the user's active household context
    memberships = await _get_user_memberships(session, user.id)
    household_id = memberships[0].household_id if memberships else None

    return jwt_service.issue_step_up_token(
        user_id=user.id,
        household_id=household_id,
        is_app_admin=user.is_app_admin,
        secret=jwt_secret,
    )


# ---------------------------------------------------------------------------
# TOTP management
# ---------------------------------------------------------------------------


async def setup_totp(session: AsyncSession, *, user: User) -> str:
    """Generate a TOTP secret and store it (not yet enabled). Returns provisioning URI."""
    secret = totp_service.generate_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    await session.flush()
    return totp_service.provisioning_uri(secret, user.email)


async def confirm_totp(session: AsyncSession, *, user: User, code: str) -> None:
    """Confirm TOTP enrollment by verifying the first code."""
    if not user.totp_secret:
        raise ConflictError("TOTP setup not started")
    if not totp_service.verify_code(user.totp_secret, code):
        raise AuthenticationError("invalid TOTP code")
    user.totp_enabled = True
    await session.flush()


# ---------------------------------------------------------------------------
# Household CRUD
# ---------------------------------------------------------------------------


async def create_household(
    session: AsyncSession,
    *,
    name: str,
    visibility_mode: VisibilityMode,
    home_currency: str,
    owner: User,
) -> Household:
    """Create a household and make the creator the owner."""
    household = Household(
        name=name,
        visibility_mode=visibility_mode,
        home_currency=home_currency.upper(),
    )
    session.add(household)
    await session.flush()

    membership = HouseholdMembership(
        household_id=household.id,
        user_id=owner.id,
        role=HouseholdRole.OWNER,
    )
    session.add(membership)
    await session.flush()

    await platform_events.fire_household_created(session, household.id)

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=owner.id,
        household_id=household.id,
        entity_type="household",
        entity_id=household.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
    )
    return household


async def get_household(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor: User,
) -> Household:
    """Return the household if the actor is a member."""
    membership = await _get_membership(session, household_id, actor.id)
    if membership is None:
        raise NotFoundError("household not found or not a member")

    result = await session.get(Household, household_id)
    if result is None:
        raise NotFoundError("household not found")
    return result


async def update_household(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor: User,
    name: str | None = None,
    visibility_mode: VisibilityMode | None = None,
    home_currency: str | None = None,
) -> Household:
    """Update mutable household fields. Actor must be owner."""
    membership = await _get_membership(session, household_id, actor.id)
    if membership is None or membership.role != HouseholdRole.OWNER:
        raise PermissionError("must be household owner to update household settings")

    household = await session.get(Household, household_id)
    if household is None:
        raise NotFoundError("household not found")

    delta: list[dict[str, Any]] = []
    if name is not None:
        delta.append({"op": "replace", "path": "/name", "value": name})
        household.name = name
    if visibility_mode is not None:
        delta.append({"op": "replace", "path": "/visibility_mode", "value": str(visibility_mode)})
        household.visibility_mode = str(visibility_mode)
    if home_currency is not None:
        delta.append({"op": "replace", "path": "/home_currency", "value": home_currency.upper()})
        household.home_currency = home_currency.upper()

    await session.flush()

    if delta:
        await _write_audit(
            session,
            actor_type=ActorType.USER,
            actor_id=actor.id,
            household_id=household.id,
            entity_type="household",
            entity_id=household.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return household


async def archive_household(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor: User,
) -> None:
    """Soft-delete a household. Actor must be owner."""
    membership = await _get_membership(session, household_id, actor.id)
    if membership is None or membership.role != HouseholdRole.OWNER:
        raise PermissionError("must be household owner to archive")

    household = await session.get(Household, household_id)
    if household is None:
        raise NotFoundError("household not found")

    now = datetime.now(tz=UTC)
    household.archived_at = now
    household.archived_by = actor.id
    await session.flush()

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor.id,
        household_id=household_id,
        entity_type="household",
        entity_id=household_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


async def list_households(session: AsyncSession, *, actor: User) -> list[Household]:
    """Return all households the actor is a member of."""
    stmt = (
        sa.select(Household)
        .join(
            HouseholdMembership,
            (HouseholdMembership.household_id == Household.id)
            & (HouseholdMembership.user_id == actor.id)
            & HouseholdMembership.archived_at.is_(None),
        )
        .order_by(Household.created_at)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


async def add_member(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    email: str,
    role: HouseholdRole,
    actor: User,
) -> HouseholdMembership:
    """Add a user to the household. Actor must be App Admin (step-up required)."""
    if not actor.is_app_admin:
        raise PermissionError("adding household members requires App Admin role")

    household = await session.get(Household, household_id)
    if household is None:
        raise NotFoundError("household not found")

    new_user = await _get_user_by_email(session, email)
    if new_user is None:
        raise NotFoundError(f"no user with email {email!r}")

    existing = await _get_membership(session, household_id, new_user.id)
    if existing is not None:
        raise ConflictError("user is already a member of this household")

    membership = HouseholdMembership(
        household_id=household_id,
        user_id=new_user.id,
        role=role,
    )
    session.add(membership)
    await session.flush()

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor.id,
        household_id=household_id,
        entity_type="household_membership",
        entity_id=membership.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/user_id", "value": str(new_user.id)},
            {"op": "add", "path": "/role", "value": str(role)},
        ],
    )
    return membership


async def remove_member(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    actor: User,
) -> None:
    """Soft-delete a membership. Actor must be App Admin."""
    if not actor.is_app_admin:
        raise PermissionError("removing members requires App Admin role")

    membership = await _get_membership(session, household_id, user_id)
    if membership is None:
        raise NotFoundError("membership not found")

    now = datetime.now(tz=UTC)
    membership.archived_at = now
    membership.archived_by = actor.id
    await session.flush()

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor.id,
        household_id=household_id,
        entity_type="household_membership",
        entity_id=membership.id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


async def list_members(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor: User,
) -> list[HouseholdMembership]:
    """Return all active memberships for a household."""
    membership = await _get_membership(session, household_id, actor.id)
    if membership is None:
        raise PermissionError("not a member of this household")

    stmt = (
        sa.select(HouseholdMembership)
        .where(HouseholdMembership.household_id == household_id)
        .order_by(HouseholdMembership.created_at)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = sa.select(User).where(User.email == email.lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def _get_membership(
    session: AsyncSession, household_id: uuid.UUID, user_id: uuid.UUID
) -> HouseholdMembership | None:
    stmt = sa.select(HouseholdMembership).where(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_user_memberships(
    session: AsyncSession, user_id: uuid.UUID
) -> list[HouseholdMembership]:
    stmt = sa.select(HouseholdMembership).where(HouseholdMembership.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_refresh_token_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    stmt = (
        sa.select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .execution_options(include_archived=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _revoke_refresh_token(session: AsyncSession, rt: RefreshToken) -> None:
    rt.revoked_at = datetime.now(tz=UTC)
    await session.flush()


async def _write_audit(
    session: AsyncSession,
    *,
    actor_type: ActorType,
    actor_id: uuid.UUID | None,
    household_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    operation: AuditOperation,
    delta: list[dict[str, Any]],
    rationale: str | None = None,
) -> None:
    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=actor_type,
        actor_source="user_action",
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        delta=delta,
        rationale=rationale,
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Sessions management
# ---------------------------------------------------------------------------


async def list_user_sessions(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[RefreshToken]:
    """Return all active (non-revoked, non-expired) refresh tokens for a user."""
    now = datetime.now(tz=UTC)
    stmt = (
        sa.select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.issued_at.desc())
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Verify current password then update to new password hash.

    Revokes all existing refresh tokens — user must re-login on all devices.
    Raises AuthenticationError if current_password is wrong.
    """
    if user.password_hash is None:
        raise AuthenticationError("no local auth configured for this user")
    if not pwd_service.verify_password(current_password, user.password_hash):
        raise AuthenticationError("invalid credentials")

    user.password_hash = pwd_service.hash_password(new_password)
    await session.flush()
    await revoke_all_tokens(session, user_id=user.id)

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=user.id,
        household_id=None,
        entity_type="user",
        entity_id=user.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/password_hash", "value": "[redacted]"}],
    )


# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------


async def update_user_profile(
    session: AsyncSession,
    *,
    user: User,
    display_name: str,
) -> User:
    """Update the user's display_name."""
    user.display_name = display_name
    await session.flush()

    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=user.id,
        household_id=None,
        entity_type="user",
        entity_id=user.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/display_name", "value": display_name}],
    )
    return user


async def revoke_user_session(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    token_id: uuid.UUID,
) -> None:
    """Revoke a specific refresh token. Verifies ownership before revoking."""
    rt = await session.get(RefreshToken, token_id)
    if rt is None or rt.user_id != user_id or rt.revoked_at is not None:
        raise NotFoundError("session not found")
    rt.revoked_at = datetime.now(tz=UTC)
    await session.flush()


# ---------------------------------------------------------------------------
# get_user_by_id is a public helper used by deps.py
# ---------------------------------------------------------------------------

get_user_by_id = _get_user_by_id
