"""ARQ background jobs for the admin module.

Fast pool jobs:
  send_admin_notification_job  -- create notification row, email all admins
  check_worker_health_job      -- every 5 minutes, ping ARQ queues

Slow pool jobs:
  run_backup_job               -- pg_dump, optional S3 upload, local retention
  check_backup_health_job      -- daily, alert if backup stale or failed
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import arq
import sqlalchemy as sa
import structlog

from app.admin.enums import BackupStatus, NotificationType
from app.database import get_session_factory

logger = structlog.get_logger(__name__)

_BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/backups"))
_WORKER_HEALTH_REDIS_KEY = "admin:worker_health_notified_at"


async def send_admin_notification_job(
    ctx: dict[str, Any],
    *,
    notification_type: str,
    title: str,
    body: str,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """Create AdminNotification row and email all admins if SMTP configured."""
    _ = ctx
    from app.admin.service import create_notification, send_email, smtp_configured
    from app.households.models import User

    eid = uuid.UUID(entity_id) if entity_id else None
    factory = get_session_factory()

    try:
        async with factory() as session:
            notif = await create_notification(
                session,
                notification_type=NotificationType(notification_type),
                title=title,
                body=body,
                entity_id=eid,
            )
            await session.commit()

            if await smtp_configured(session):
                result = await session.execute(
                    sa.select(User).where(User.is_app_admin.is_(True), User.archived_at.is_(None))
                )
                admins = list(result.scalars().all())
                for admin in admins:
                    await send_email(
                        session,
                        to=admin.email,
                        subject=f"[WDIAG] {title}",
                        body_text=body,
                    )

        return {"notification_id": str(notif.id)}
    except Exception as exc:
        logger.error("send_admin_notification_job.failed", error=str(exc))
        return {"error": str(exc)}


async def run_backup_job(
    ctx: dict[str, Any],
    *,
    backup_run_id: str,
) -> dict[str, Any]:
    """Execute pg_dump, optionally upload to S3, apply local retention."""
    _ = ctx
    from app.admin.models import BackupRun
    from app.admin.service import get_backup_config
    from app.config import get_settings
    from app.security.encryption import decrypt_dict

    run_id = uuid.UUID(backup_run_id)
    factory = get_session_factory()
    settings = get_settings()

    async with factory() as session:
        result = await session.execute(sa.select(BackupRun).where(BackupRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            logger.error("run_backup_job.not_found", backup_run_id=backup_run_id)
            return {"error": "backup run not found"}

        try:
            _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            filename = f"wdiag_{ts}.sql.gz"
            local_path = _BACKUP_DIR / filename

            db_url = str(settings.database_url)
            proc = subprocess.run(  # noqa: S603
                ["pg_dump", db_url],  # noqa: S607
                capture_output=True,
                check=True,
                timeout=3600,
            )
            import gzip

            with gzip.open(local_path, "wb") as f:
                f.write(proc.stdout)

            size_bytes = local_path.stat().st_size
            run.size_bytes = size_bytes
            run.local_path = str(local_path)

            cfg = await get_backup_config(session)
            s3_path: str | None = None
            if cfg and cfg.s3_enabled and cfg.s3_bucket:
                try:
                    endpoint = None
                    access_key = None
                    secret_key = None
                    if cfg.s3_endpoint_enc:
                        endpoint = decrypt_dict(cfg.s3_endpoint_enc, settings.master_key)["v"]
                    if cfg.s3_access_key_enc:
                        access_key = decrypt_dict(cfg.s3_access_key_enc, settings.master_key)["v"]
                    if cfg.s3_secret_key_enc:
                        secret_key = decrypt_dict(cfg.s3_secret_key_enc, settings.master_key)["v"]

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
                    key = f"{cfg.s3_path_prefix}/{filename}"
                    s3.upload_file(str(local_path), cfg.s3_bucket, key)
                    s3_path = f"s3://{cfg.s3_bucket}/{key}"
                    run.s3_path = s3_path
                except Exception as s3_exc:
                    logger.error("run_backup_job.s3_upload_failed", error=str(s3_exc))

            run.status = BackupStatus.SUCCESS
            run.completed_at = datetime.now(tz=UTC)
            await session.commit()

            if cfg:
                _apply_local_retention(cfg.local_retention_days)

            logger.info(
                "run_backup_job.success",
                backup_run_id=backup_run_id,
                size_bytes=size_bytes,
                s3_path=s3_path,
            )
            return {"status": "success", "size_bytes": size_bytes}

        except Exception as exc:
            logger.error("run_backup_job.failed", backup_run_id=backup_run_id, error=str(exc))
            run.status = BackupStatus.FAILED
            run.completed_at = datetime.now(tz=UTC)
            run.error_detail = str(exc)
            await session.commit()

            pool = await _get_pool()
            await pool.enqueue_job(
                "send_admin_notification_job",
                notification_type=NotificationType.BACKUP_FAILED,
                title="Backup failed",
                body=f"Backup run {backup_run_id} failed: {exc}",
            )
            await pool.aclose()
            return {"status": "failed", "error": str(exc)}


def _apply_local_retention(retention_days: int) -> None:
    """Delete local backup files older than retention_days."""
    from datetime import timedelta

    if not _BACKUP_DIR.exists():
        return
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    for f in _BACKUP_DIR.glob("wdiag_*.sql.gz"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                f.unlink()
                logger.info("run_backup_job.deleted_old_backup", path=str(f))
        except Exception as exc:
            logger.warning("run_backup_job.delete_old_failed", path=str(f), error=str(exc))


async def check_worker_health_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Ping ARQ queues; notify once per outage window."""
    _ = ctx
    from app.config import get_settings

    settings = get_settings()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        healthy = await r.ping()

        if not healthy:
            last_notified = await r.get(_WORKER_HEALTH_REDIS_KEY)
            if last_notified is None:
                await r.set(_WORKER_HEALTH_REDIS_KEY, datetime.now(tz=UTC).isoformat(), ex=3600)
                pool = await _get_pool()
                await pool.enqueue_job(
                    "send_admin_notification_job",
                    notification_type=NotificationType.SYSTEM_ERROR,
                    title="Worker health check failed",
                    body="ARQ worker did not respond to ping.",
                )
                await pool.aclose()
        else:
            await r.delete(_WORKER_HEALTH_REDIS_KEY)

        await r.aclose()
        return {"healthy": healthy}
    except Exception as exc:
        logger.error("check_worker_health_job.error", error=str(exc))
        return {"error": str(exc)}


async def check_backup_health_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Alert if last backup is missing, stale, or failed."""
    _ = ctx
    from app.admin.models import BackupRun

    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            sa.select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1)
        )
        last_run = result.scalar_one_or_none()

        needs_alert = False
        if last_run is None:
            needs_alert = True
        else:
            from datetime import timedelta

            age = datetime.now(tz=UTC) - last_run.started_at.replace(tzinfo=UTC)
            if age > timedelta(hours=25) or last_run.status == BackupStatus.FAILED:
                needs_alert = True

        if needs_alert:
            pool = await _get_pool()
            await pool.enqueue_job(
                "send_admin_notification_job",
                notification_type=NotificationType.BACKUP_FAILED,
                title="Backup health alert",
                body=(
                    "No recent successful backup found. "
                    f"Last run: {last_run.started_at if last_run else 'never'}"
                ),
            )
            await pool.aclose()
            logger.warning("check_backup_health_job.alert_sent")

    return {"needs_alert": needs_alert}


async def _get_pool() -> arq.ArqRedis:
    from app.worker.settings import get_redis_settings

    return await arq.create_pool(get_redis_settings())
