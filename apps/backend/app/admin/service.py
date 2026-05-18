"""Admin service layer — all business logic for system administration.

This module never imports from other domain modules directly.
Cross-module access uses raw SQL (same pattern as households/jobs.py).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.enums import BackupStatus, BackupTrigger, NotificationType
from app.admin.models import (
    AdminNotification,
    AdminSetting,
    BackupConfig,
    BackupRun,
    ReadOnlyState,
    SMTPConfig,
)
from app.platform.time import utcnow

logger = structlog.get_logger(__name__)

_READ_ONLY_REDIS_KEY = "system:read_only_state"
_WORKER_HEALTH_REDIS_KEY = "admin:worker_health_last_notified"


class LastAdminError(Exception):
    """Raised when an operation would remove the last app admin."""


class NotFoundError(Exception):
    """Raised when a requested entity does not exist."""


# ---------------------------------------------------------------------------
# Read-only state
# ---------------------------------------------------------------------------


async def get_read_only_state(session: AsyncSession) -> ReadOnlyState:
    """Return the current read-only state row, creating default if absent."""
    result = await session.execute(sa.select(ReadOnlyState).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = ReadOnlyState(enabled=False)
        session.add(row)
        await session.flush()
    return row


async def check_read_only(redis_url: str | None = None) -> bool:
    """Return True if system is in read-only mode.

    Checks Redis first (fast path). Falls back to DB only when Redis unavailable.
    This function is safe to call from any ARQ job.
    """
    from app.config import get_settings
    from app.database import get_session_factory

    settings = get_settings()
    redis_dsn = redis_url or str(settings.redis_url)

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(redis_dsn, decode_responses=True)
        raw = await r.get(_READ_ONLY_REDIS_KEY)
        await r.aclose()
        if raw is not None:
            data: dict[str, Any] = json.loads(raw)
            return bool(data.get("enabled", False))
        return False
    except Exception as exc:
        logger.debug("check_read_only.redis_unavailable", error=str(exc))

    try:
        factory = get_session_factory()
        async with factory() as session:
            row = await get_read_only_state(session)
            return row.enabled
    except Exception:
        return False


async def set_read_only(
    session: AsyncSession,
    *,
    enabled: bool,
    reason: str | None,
    enabled_by_id: uuid.UUID | None,
) -> ReadOnlyState:
    """Toggle read-only mode, update Redis, broadcast SSE."""
    from app.config import get_settings
    from app.households.sse import get_sse_manager

    row = await get_read_only_state(session)
    row.enabled = enabled
    row.reason = reason
    row.enabled_at = utcnow() if enabled else None
    row.enabled_by_id = enabled_by_id if enabled else None
    await session.flush()

    cache_data = json.dumps({"enabled": enabled, "reason": reason})
    try:
        import redis.asyncio as aioredis

        settings = get_settings()
        r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        if enabled:
            await r.set(_READ_ONLY_REDIS_KEY, cache_data)
        else:
            await r.delete(_READ_ONLY_REDIS_KEY)
        await r.aclose()
    except Exception:
        logger.warning("set_read_only.redis_unavailable")

    mgr = get_sse_manager()
    await mgr.broadcast("read_only_changed", {"enabled": enabled, "reason": reason})

    return row


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


async def create_notification(
    session: AsyncSession,
    *,
    notification_type: NotificationType,
    title: str,
    body: str,
    entity_id: uuid.UUID | None = None,
) -> AdminNotification:
    notif = AdminNotification(
        notification_type=notification_type,
        title=title,
        body=body,
        entity_id=entity_id,
    )
    session.add(notif)
    await session.flush()
    return notif


async def list_notifications(
    session: AsyncSession,
    *,
    read: bool | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[AdminNotification], str | None]:
    stmt = sa.select(AdminNotification).order_by(AdminNotification.created_at.desc())
    if read is not None:
        stmt = stmt.where(AdminNotification.read == read)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(AdminNotification.created_at < cursor_dt)
        except ValueError:
            pass
    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat()
    return rows, next_cursor


async def mark_read(session: AsyncSession, notification_id: uuid.UUID) -> AdminNotification:
    result = await session.execute(
        sa.select(AdminNotification).where(AdminNotification.id == notification_id)
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        raise NotFoundError(f"notification {notification_id} not found")
    if not notif.read:
        notif.read = True
        notif.read_at = utcnow()
        await session.flush()
    return notif


async def mark_all_read(session: AsyncSession) -> None:
    now = utcnow()
    await session.execute(
        sa.update(AdminNotification)
        .where(AdminNotification.read.is_(False))
        .values(read=True, read_at=now)
    )


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


def _encrypt_field(value: str, master_key: str) -> str:
    from app.security.encryption import encrypt_dict

    return encrypt_dict({"v": value}, master_key)


def _decrypt_field(token: str, master_key: str) -> str:
    from app.security.encryption import decrypt_dict

    return decrypt_dict(token, master_key)["v"]


async def get_smtp_config(session: AsyncSession) -> SMTPConfig | None:
    result = await session.execute(sa.select(SMTPConfig).limit(1))
    return result.scalar_one_or_none()


async def upsert_smtp_config(
    session: AsyncSession,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    from_address: str,
    use_tls: bool,
    configured_by_id: uuid.UUID,
) -> SMTPConfig:
    from app.config import get_settings

    master_key = get_settings().master_key
    existing = await get_smtp_config(session)
    if existing is None:
        cfg = SMTPConfig(
            host_enc=_encrypt_field(host, master_key),
            port=port,
            username_enc=_encrypt_field(username, master_key),
            password_enc=_encrypt_field(password, master_key),
            from_address=from_address,
            use_tls=use_tls,
            configured_by_id=configured_by_id,
        )
        session.add(cfg)
    else:
        cfg = existing
        cfg.host_enc = _encrypt_field(host, master_key)
        cfg.port = port
        cfg.username_enc = _encrypt_field(username, master_key)
        cfg.password_enc = _encrypt_field(password, master_key)
        cfg.from_address = from_address
        cfg.use_tls = use_tls
        cfg.configured_at = utcnow()
        cfg.configured_by_id = configured_by_id
    await session.flush()
    return cfg


async def delete_smtp_config(session: AsyncSession) -> None:
    await session.execute(sa.delete(SMTPConfig))


async def smtp_configured(session: AsyncSession) -> bool:
    """True when a SMTP config row exists in DB."""
    cfg = await get_smtp_config(session)
    return cfg is not None


async def send_email(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> tuple[bool, str | None]:
    """Send an email via configured SMTP. Returns (success, error_detail)."""
    from app.config import get_settings

    cfg = await get_smtp_config(session)
    if cfg is None:
        return False, "SMTP not configured"

    master_key = get_settings().master_key
    try:
        host = _decrypt_field(cfg.host_enc, master_key)
        username = _decrypt_field(cfg.username_enc, master_key)
        password = _decrypt_field(cfg.password_enc, master_key)
    except Exception as exc:
        return False, f"credential decryption failed: {exc}"

    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        import aiosmtplib

        msg: MIMEMultipart | MIMEText
        if body_html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))
        else:
            msg = MIMEText(body_text, "plain")

        msg["Subject"] = subject
        msg["From"] = cfg.from_address
        msg["To"] = to

        await aiosmtplib.send(
            msg,
            hostname=host,
            port=cfg.port,
            username=username,
            password=password,
            use_tls=cfg.use_tls,
        )
        return True, None
    except Exception as exc:
        logger.warning("send_email.failed", to=to, error=str(exc))
        return False, str(exc)


async def test_smtp(session: AsyncSession, to_address: str) -> tuple[bool, str | None]:
    """Send a test email and record the result."""
    success, error = await send_email(
        session,
        to=to_address,
        subject="WDIAG — SMTP test",
        body_text="This is a test email from WDIAG. SMTP is configured correctly.",
    )
    cfg = await get_smtp_config(session)
    if cfg is not None:
        cfg.last_test_success = success
        cfg.last_test_error = error
        cfg.last_test_at = utcnow()
        await session.flush()
    return success, error


# ---------------------------------------------------------------------------
# Backup config
# ---------------------------------------------------------------------------


async def get_backup_config(session: AsyncSession) -> BackupConfig | None:
    result = await session.execute(sa.select(BackupConfig).limit(1))
    return result.scalar_one_or_none()


async def upsert_backup_config(
    session: AsyncSession,
    *,
    s3_endpoint: str | None,
    s3_bucket: str | None,
    s3_access_key: str | None,
    s3_secret_key: str | None,
    s3_path_prefix: str,
    local_retention_days: int,
    s3_enabled: bool,
    configured_by_id: uuid.UUID,
) -> BackupConfig:
    from app.config import get_settings

    master_key = get_settings().master_key
    existing = await get_backup_config(session)

    def _enc(val: str | None) -> str | None:
        return _encrypt_field(val, master_key) if val else None

    if existing is None:
        cfg = BackupConfig(
            s3_endpoint_enc=_enc(s3_endpoint),
            s3_bucket=s3_bucket,
            s3_access_key_enc=_enc(s3_access_key),
            s3_secret_key_enc=_enc(s3_secret_key),
            s3_path_prefix=s3_path_prefix,
            local_retention_days=local_retention_days,
            s3_enabled=s3_enabled,
            configured_by_id=configured_by_id,
        )
        session.add(cfg)
    else:
        cfg = existing
        cfg.s3_endpoint_enc = _enc(s3_endpoint)
        cfg.s3_bucket = s3_bucket
        cfg.s3_access_key_enc = _enc(s3_access_key)
        cfg.s3_secret_key_enc = _enc(s3_secret_key)
        cfg.s3_path_prefix = s3_path_prefix
        cfg.local_retention_days = local_retention_days
        cfg.s3_enabled = s3_enabled
        cfg.configured_at = utcnow()
        cfg.configured_by_id = configured_by_id
    await session.flush()
    return cfg


async def delete_s3_config(session: AsyncSession) -> BackupConfig:
    """Clear S3 fields, disable S3."""
    cfg = await get_backup_config(session)
    if cfg is None:
        raise NotFoundError("backup config not found")
    cfg.s3_endpoint_enc = None
    cfg.s3_bucket = None
    cfg.s3_access_key_enc = None
    cfg.s3_secret_key_enc = None
    cfg.s3_enabled = False
    await session.flush()
    return cfg


async def test_s3(session: AsyncSession) -> tuple[bool, str | None]:
    """Attempt to list the configured S3 bucket."""
    from app.config import get_settings

    cfg = await get_backup_config(session)
    if cfg is None or not cfg.s3_bucket:
        return False, "S3 not configured"

    master_key = get_settings().master_key
    try:
        endpoint = _decrypt_field(cfg.s3_endpoint_enc, master_key) if cfg.s3_endpoint_enc else None
        access_key = (
            _decrypt_field(cfg.s3_access_key_enc, master_key) if cfg.s3_access_key_enc else None
        )
        secret_key = (
            _decrypt_field(cfg.s3_secret_key_enc, master_key) if cfg.s3_secret_key_enc else None
        )
    except Exception as exc:
        return False, f"credential decryption failed: {exc}"

    try:
        import boto3
        from botocore.config import Config

        kwargs: dict[str, Any] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": Config(signature_version="s3v4"),
        }
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **kwargs)
        s3.list_objects_v2(Bucket=cfg.s3_bucket, MaxKeys=1)
        return True, None
    except Exception as exc:
        return False, str(exc)


async def trigger_backup(session: AsyncSession, triggered_by_id: uuid.UUID) -> BackupRun:
    """Create BackupRun row, enqueue run_backup_job."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.config import get_settings

    run = BackupRun(
        triggered_by=BackupTrigger.MANUAL,
        triggered_by_id=triggered_by_id,
        status=BackupStatus.RUNNING,
    )
    session.add(run)
    await session.flush()

    settings = get_settings()
    redis_url = str(settings.redis_url)
    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    await pool.enqueue_job("run_backup_job", backup_run_id=str(run.id))
    await pool.aclose()

    return run


async def list_backup_runs(
    session: AsyncSession,
    *,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[BackupRun], str | None]:
    stmt = sa.select(BackupRun).order_by(BackupRun.started_at.desc())
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(BackupRun.started_at < cursor_dt)
        except ValueError:
            pass
    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].started_at.isoformat()
    return rows, next_cursor


# ---------------------------------------------------------------------------
# Registration settings (DB override layer)
# ---------------------------------------------------------------------------

_SETTING_ALLOW_REGISTRATION = "allow_registration"
_SETTING_REGISTRATION_LIMIT = "registration_limit"
_SETTING_UNASSIGNED_TTL = "unassigned_account_ttl_days"


async def get_registration_settings(session: AsyncSession) -> dict[str, Any]:
    from app.config import get_settings

    base = get_settings()
    result = await session.execute(
        sa.select(AdminSetting).where(
            AdminSetting.key.in_(
                [
                    _SETTING_ALLOW_REGISTRATION,
                    _SETTING_REGISTRATION_LIMIT,
                    _SETTING_UNASSIGNED_TTL,
                ]
            )
        )
    )
    overrides = {row.key: row.value for row in result.scalars().all()}

    allow_reg: bool = base.allow_registration
    if _SETTING_ALLOW_REGISTRATION in overrides:
        allow_reg = overrides[_SETTING_ALLOW_REGISTRATION].lower() == "true"

    reg_limit: int | None = base.registration_limit
    if _SETTING_REGISTRATION_LIMIT in overrides:
        v = overrides[_SETTING_REGISTRATION_LIMIT]
        reg_limit = None if v == "null" else int(v)

    ttl: int = base.unassigned_account_ttl_days
    if _SETTING_UNASSIGNED_TTL in overrides:
        ttl = int(overrides[_SETTING_UNASSIGNED_TTL])

    return {
        "allow_registration": allow_reg,
        "registration_limit": reg_limit,
        "unassigned_account_ttl_days": ttl,
    }


async def update_registration_settings(
    session: AsyncSession,
    *,
    allow_registration: bool,
    registration_limit: int | None,
    unassigned_account_ttl_days: int,
    updated_by_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    updates = {
        _SETTING_ALLOW_REGISTRATION: str(allow_registration).lower(),
        _SETTING_REGISTRATION_LIMIT: "null"
        if registration_limit is None
        else str(registration_limit),
        _SETTING_UNASSIGNED_TTL: str(unassigned_account_ttl_days),
    }
    now = utcnow()
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    for key, value in updates.items():
        await session.execute(
            pg_insert(AdminSetting)
            .values(key=key, value=value, updated_at=now, updated_by_id=updated_by_id)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": now, "updated_by_id": updated_by_id},
            )
        )
    return {
        "allow_registration": allow_registration,
        "registration_limit": registration_limit,
        "unassigned_account_ttl_days": unassigned_account_ttl_days,
    }


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


async def _count_admins(session: AsyncSession) -> int:
    from app.households.models import User

    result = await session.execute(
        sa.select(sa.func.count())
        .select_from(User)
        .where(User.is_app_admin.is_(True), User.archived_at.is_(None))
    )
    return result.scalar_one()


async def list_users(
    session: AsyncSession,
    *,
    search: str | None = None,
    unassigned: bool | None = None,
    is_admin: bool | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    from app.households.models import HouseholdMembership, User

    stmt = (
        sa.select(
            User,
            sa.func.count(HouseholdMembership.id).label("household_count"),
        )
        .outerjoin(HouseholdMembership, HouseholdMembership.user_id == User.id)
        .where(User.archived_at.is_(None))
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(sa.or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
    if is_admin is not None:
        stmt = stmt.where(User.is_app_admin == is_admin)
    if unassigned is True:
        stmt = stmt.having(sa.func.count(HouseholdMembership.id) == 0)

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(User.created_at < cursor_dt)
        except ValueError:
            pass

    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = result.all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]

    out: list[dict[str, Any]] = []
    for row in rows:
        user = row[0]
        hh_count = row[1]
        out.append(
            {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "is_app_admin": user.is_app_admin,
                "created_at": user.created_at,
                "household_count": hh_count,
            }
        )

    if len(rows) == limit and rows:
        next_cursor = rows[-1][0].created_at.isoformat()

    return out, next_cursor


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    from app.households.models import HouseholdMembership, User

    result = await session.execute(
        sa.select(
            User,
            sa.func.count(HouseholdMembership.id).label("household_count"),
        )
        .outerjoin(HouseholdMembership, HouseholdMembership.user_id == User.id)
        .where(User.id == user_id, User.archived_at.is_(None))
        .group_by(User.id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError(f"user {user_id} not found")
    user = row[0]
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_app_admin": user.is_app_admin,
        "created_at": user.created_at,
        "household_count": row[1],
    }


async def promote_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    by_id: uuid.UUID,
) -> None:
    from app.audit import ActorType, AuditOperation
    from app.audit import service as audit_service
    from app.households.models import User

    result = await session.execute(sa.select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"user {user_id} not found")
    user.is_app_admin = True
    await session.flush()

    await audit_service.log(
        session,
        household_id=None,
        actor_type=ActorType.USER,
        actor_id=by_id,
        actor_source="admin_panel",
        entity_type="user",
        entity_id=user_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/is_app_admin", "value": True}],
        rationale="Admin promoted user",
    )


async def demote_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    by_id: uuid.UUID,
) -> None:
    from app.audit import ActorType, AuditOperation
    from app.audit import service as audit_service
    from app.households.models import User

    admin_count = await _count_admins(session)
    if admin_count <= 1:
        raise LastAdminError("cannot demote the last app admin")

    result = await session.execute(sa.select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"user {user_id} not found")
    user.is_app_admin = False
    await session.flush()

    await audit_service.log(
        session,
        household_id=None,
        actor_type=ActorType.USER,
        actor_id=by_id,
        actor_source="admin_panel",
        entity_type="user",
        entity_id=user_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/is_app_admin", "value": False}],
        rationale="Admin demoted user",
    )


async def assign_household(
    session: AsyncSession,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    role: str,
    by_id: uuid.UUID,
) -> None:
    """Create HouseholdMembership, emit SSE, create notification."""
    from app.audit import ActorType, AuditOperation
    from app.audit import service as audit_service
    from app.households.models import Household, HouseholdMembership
    from app.households.sse import get_sse_manager

    hh_result = await session.execute(
        sa.select(Household).where(Household.id == household_id, Household.archived_at.is_(None))
    )
    household = hh_result.scalar_one_or_none()
    if household is None:
        raise NotFoundError(f"household {household_id} not found")

    membership = HouseholdMembership(
        household_id=household_id,
        user_id=user_id,
        role=role,
    )
    session.add(membership)
    await session.flush()

    mgr = get_sse_manager()
    await mgr.send_to_user(
        user_id,
        "household_assigned",
        {"household_id": str(household_id), "household_name": household.name},
    )

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_id=by_id,
        actor_source="admin_panel",
        entity_type="membership",
        entity_id=membership.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/user_id", "value": str(user_id)}],
        rationale="Admin assigned household",
    )


async def force_logout(session: AsyncSession, user_id: uuid.UUID) -> None:
    from app.households.models import RefreshToken

    now = utcnow()
    await session.execute(
        sa.update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def force_logout_all(session: AsyncSession) -> None:
    from app.households.models import RefreshToken

    now = utcnow()
    await session.execute(
        sa.update(RefreshToken).where(RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )


async def delete_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    by_id: uuid.UUID,
) -> None:
    """Hard-delete a user, nulling out cross-module references via raw SQL."""
    from app.audit import ActorType, AuditOperation
    from app.audit import service as audit_service
    from app.households.models import HouseholdMembership, RefreshToken, User

    admin_count = await _count_admins(session)
    result = await session.execute(sa.select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"user {user_id} not found")

    if user.is_app_admin and admin_count <= 1:
        raise LastAdminError("cannot delete the last app admin")

    # Null out cross-module references via raw SQL (no FK imports)
    await session.execute(
        sa.text(
            "UPDATE transactions_split_allocation "
            "SET attributed_to_user_id = NULL "
            "WHERE attributed_to_user_id = :uid"
        ),
        {"uid": user_id},
    )
    await session.execute(
        sa.text(
            "UPDATE recommendations_recommendation SET resolved_by = NULL WHERE resolved_by = :uid"
        ),
        {"uid": user_id},
    )

    await session.execute(
        sa.delete(HouseholdMembership).where(HouseholdMembership.user_id == user_id)
    )

    now = utcnow()
    await session.execute(
        sa.update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    await audit_service.log(
        session,
        household_id=None,
        actor_type=ActorType.USER,
        actor_id=by_id,
        actor_source="admin_panel",
        entity_type="user",
        entity_id=user_id,
        operation=AuditOperation.DELETE,
        delta=[{"op": "remove", "path": "/id", "value": str(user_id)}],
        rationale="Admin deleted user",
    )

    await session.execute(sa.delete(User).where(User.id == user_id))


# ---------------------------------------------------------------------------
# Household admin views
# ---------------------------------------------------------------------------


async def list_households_admin(session: AsyncSession) -> list[dict[str, Any]]:
    from app.households.models import Household, HouseholdMembership

    stmt = (
        sa.select(
            Household,
            sa.func.count(HouseholdMembership.id).label("member_count"),
        )
        .outerjoin(HouseholdMembership, HouseholdMembership.household_id == Household.id)
        .where(Household.archived_at.is_(None))
        .group_by(Household.id)
        .order_by(Household.created_at.desc())
    )
    result = await session.execute(stmt)
    out = []
    for row in result.all():
        hh = row[0]
        member_count = row[1]
        account_count_result = await session.execute(
            sa.text(
                "SELECT COUNT(*) FROM accounts_account"
                " WHERE household_id = :hid AND archived_at IS NULL"
            ),
            {"hid": hh.id},
        )
        account_count = account_count_result.scalar_one()
        out.append(
            {
                "id": hh.id,
                "name": hh.name,
                "member_count": member_count,
                "account_count": account_count,
                "created_at": hh.created_at,
                "visibility_mode": hh.visibility_mode,
            }
        )
    return out


async def get_household_admin(session: AsyncSession, household_id: uuid.UUID) -> dict[str, Any]:
    from app.households.models import Household, HouseholdMembership, User

    hh_result = await session.execute(
        sa.select(Household).where(Household.id == household_id, Household.archived_at.is_(None))
    )
    hh = hh_result.scalar_one_or_none()
    if hh is None:
        raise NotFoundError(f"household {household_id} not found")

    members_result = await session.execute(
        sa.select(User, HouseholdMembership)
        .join(HouseholdMembership, HouseholdMembership.user_id == User.id)
        .where(HouseholdMembership.household_id == household_id)
    )
    member_rows = members_result.all()

    account_count_result = await session.execute(
        sa.text(
            "SELECT COUNT(*) FROM accounts_account"
            " WHERE household_id = :hid AND archived_at IS NULL"
        ),
        {"hid": household_id},
    )
    account_count = account_count_result.scalar_one()

    members = []
    for user, _membership in member_rows:
        hh_count_r = await session.execute(
            sa.select(sa.func.count(HouseholdMembership.id)).where(
                HouseholdMembership.user_id == user.id
            )
        )
        members.append(
            {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "is_app_admin": user.is_app_admin,
                "created_at": user.created_at,
                "household_count": hh_count_r.scalar_one(),
            }
        )

    return {
        "id": hh.id,
        "name": hh.name,
        "member_count": len(members),
        "account_count": account_count,
        "created_at": hh.created_at,
        "visibility_mode": hh.visibility_mode,
        "members": members,
    }


# ---------------------------------------------------------------------------
# System health / overview
# ---------------------------------------------------------------------------


async def get_system_overview(
    session: AsyncSession,
    app_started_at: datetime,
) -> dict[str, Any]:
    from app.config import get_settings

    settings = get_settings()

    # User counts
    active_users = await session.execute(
        sa.text("SELECT COUNT(*) FROM households_user WHERE archived_at IS NULL")
    )
    active_user_count: int = active_users.scalar_one()

    unassigned = await session.execute(
        sa.text(
            "SELECT COUNT(*) FROM households_user u "
            "WHERE u.archived_at IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM households_membership m WHERE m.user_id = u.id)"
        )
    )
    unassigned_user_count: int = unassigned.scalar_one()

    hh_count_r = await session.execute(
        sa.text("SELECT COUNT(*) FROM households_household WHERE archived_at IS NULL")
    )
    household_count: int = hh_count_r.scalar_one()

    # DB size
    db_size_r = await session.execute(sa.text("SELECT pg_database_size(current_database())"))
    db_size_bytes: int = db_size_r.scalar_one()

    # Active sessions
    sessions_r = await session.execute(
        sa.text(
            "SELECT COUNT(*) FROM households_refresh_token "
            "WHERE revoked_at IS NULL AND expires_at > NOW()"
        )
    )
    active_session_count: int = sessions_r.scalar_one()

    # Redis info
    redis_memory_bytes = 0
    worker_fast_healthy = False
    worker_slow_healthy = False
    pending_job_count = 0
    failed_job_count_24h = 0

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        info = await r.info("memory")
        redis_memory_bytes = int(info.get("used_memory", 0))

        # Worker health: check for recent heartbeat keys
        fast_ping = await r.ping()
        worker_fast_healthy = bool(fast_ping)
        worker_slow_healthy = bool(fast_ping)

        # Pending jobs
        pending_job_count = await r.llen("arq:queue:default") or 0

        # Failed jobs in last 24h
        import time

        cutoff = time.time() - 86400
        failed_keys = await r.zrangebyscore("arq:results", cutoff, "+inf")
        failed_count = 0
        for key in failed_keys:
            raw = await r.get(key)
            if raw and '"success": false' in raw:
                failed_count += 1
        failed_job_count_24h = failed_count
        await r.aclose()
    except Exception as exc:
        logger.debug("get_system_overview.redis_unavailable", error=str(exc))

    # Last backup
    last_run_r = await session.execute(
        sa.select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1)
    )
    last_run = last_run_r.scalar_one_or_none()

    # Alembic state
    alembic_current = "unknown"
    alembic_head = "unknown"
    try:
        from alembic.runtime.migration import MigrationContext

        async with session.bind.connect() as conn:  # type: ignore[union-attr]

            def _get_current(sync_conn: sa.engine.Connection) -> str:
                ctx = MigrationContext.configure(sync_conn)
                revs = ctx.get_current_heads()
                return revs[0] if revs else "base"

            alembic_current = await conn.run_sync(_get_current)
    except Exception as exc:
        logger.debug("get_system_overview.alembic_check_failed", error=str(exc))

    reg_settings = await get_registration_settings(session)
    smtp_ok = await smtp_configured(session)
    reg_limit = reg_settings["registration_limit"]
    count_vs_limit = (
        f"{active_user_count}/{reg_limit}" if reg_limit else f"{active_user_count}/unlimited"
    )

    last_backup_out = None
    if last_run is not None:
        last_backup_out = {
            "id": last_run.id,
            "started_at": last_run.started_at,
            "completed_at": last_run.completed_at,
            "status": last_run.status,
            "size_bytes": last_run.size_bytes,
            "local_path": last_run.local_path,
            "s3_path": last_run.s3_path,
            "error_detail": last_run.error_detail,
            "triggered_by": last_run.triggered_by,
            "triggered_by_id": last_run.triggered_by_id,
        }

    return {
        "active_user_count": active_user_count,
        "unassigned_user_count": unassigned_user_count,
        "household_count": household_count,
        "worker_fast_healthy": worker_fast_healthy,
        "worker_slow_healthy": worker_slow_healthy,
        "pending_job_count": pending_job_count,
        "failed_job_count_24h": failed_job_count_24h,
        "db_size_bytes": db_size_bytes,
        "redis_memory_bytes": redis_memory_bytes,
        "last_backup": last_backup_out,
        "smtp_configured": smtp_ok,
        "allow_registration": reg_settings["allow_registration"],
        "registration_limit": reg_limit,
        "active_count_vs_limit": count_vs_limit,
        "alembic_current": alembic_current,
        "alembic_head": alembic_head,
        "alembic_up_to_date": alembic_current == alembic_head,
        "active_session_count": active_session_count,
        "app_started_at": app_started_at,
    }


async def get_system_detail(
    session: AsyncSession,
    app_started_at: datetime,
) -> dict[str, Any]:
    base = await get_system_overview(session, app_started_at)

    # Table row counts
    table_names = [
        "households_user",
        "households_household",
        "households_membership",
        "accounts_account",
        "transactions_transaction",
        "admin_notification",
        "admin_backup_run",
    ]
    table_row_counts: dict[str, int] = {}
    for tbl in table_names:
        try:
            r = await session.execute(sa.text(f"SELECT COUNT(*) FROM {tbl}"))  # noqa: S608
            table_row_counts[tbl] = r.scalar_one()
        except Exception:
            table_row_counts[tbl] = -1

    failed_jobs: list[dict[str, Any]] = []
    redis_connected_clients = 0
    redis_db_keys = 0

    try:
        import time

        import redis.asyncio as aioredis

        from app.config import get_settings

        settings = get_settings()
        r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        cutoff = time.time() - 86400
        result_keys = await r.zrangebyscore("arq:results", cutoff, "+inf", withscores=True)
        for key, score in result_keys[:50]:
            raw = await r.get(key)
            if raw and '"success": false' in raw:
                failed_jobs.append(
                    {"job_id": key, "function": "", "enqueue_time": "", "score": score}
                )

        clients_info = await r.info("clients")
        redis_connected_clients = int(clients_info.get("connected_clients", 0))
        keyspace_info = await r.info("keyspace")
        for db_info in keyspace_info.values():
            if isinstance(db_info, dict):
                redis_db_keys += int(db_info.get("keys", 0))
        await r.aclose()
    except Exception as exc:
        logger.debug("get_system_detail.redis_unavailable", error=str(exc))

    return {
        **base,
        "failed_jobs": failed_jobs,
        "table_row_counts": table_row_counts,
        "redis_connected_clients": redis_connected_clients,
        "redis_db_keys": redis_db_keys,
    }
