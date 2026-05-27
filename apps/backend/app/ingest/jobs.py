"""ARQ background jobs for the ingest module.

Jobs registered in app.worker.slow (worker-slow pool — long jobs, low concurrency).

All jobs are idempotent: re-running after a crash is safe because:
  - sync_account_job: process_dedup and external_id uniqueness prevent double-inserts
  - process_upload_job: same external_id check (content-hashed for CSV, FITID for OFX)

File bytes are base64-encoded in the job payload (ARQ uses JSON serialization).
Bytes are processed in-memory and never written to the DB.
"""

import base64
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
import structlog

from app.database import get_session_factory
from app.ingest import service
from app.ingest.enums import ImportSource
from app.ingest.models import SyncConfig
from app.ingest.pipeline import run_pipeline

logger = structlog.get_logger(__name__)

_SIMPLEFIN_LOOKBACK_DAYS = 30
_SIMPLEFIN_INITIAL_LOOKBACK_DAYS = 90
_RATE_LIMIT_BACKOFF_HOURS = 25
_REQUESTS_WARNING_THRESHOLD = 20


async def _run_simplefin_sync(
    sync_config_id: str,
    lookback_days: int = _SIMPLEFIN_LOOKBACK_DAYS,
    trigger_import_job_id: str | None = None,
) -> dict[str, Any]:
    """Core SimpleFIN sync logic. Returns result dict."""
    from app.accounts.models import Account
    from app.config import get_settings
    from app.ingest.parsers.simplefin import fetch_transactions

    config_id = uuid.UUID(sync_config_id)
    trigger_job_id = uuid.UUID(trigger_import_job_id) if trigger_import_job_id else None
    logger.info("sync_account_job.start", sync_config_id=sync_config_id)

    factory = get_session_factory()
    settings = get_settings()

    if trigger_job_id:
        async with factory() as run_session:
            await service.mark_job_running(run_session, job_id=trigger_job_id)
            await run_session.commit()

    async with factory() as session:
        result = await session.execute(sa.select(SyncConfig).where(SyncConfig.id == config_id))
        config = result.scalar_one_or_none()
        if config is None:
            if trigger_job_id:
                await service.mark_job_failed(
                    session, job_id=trigger_job_id, error="sync config not found"
                )
                await session.commit()
            logger.error("sync_account_job.config_not_found", sync_config_id=sync_config_id)
            return {"error": "sync config not found"}

        if not config.sync_enabled or config.status == "disabled":
            if trigger_job_id:
                await service.mark_job_failed(session, job_id=trigger_job_id, error="sync disabled")
                await session.commit()
            logger.info("sync_account_job.skipped_disabled", sync_config_id=sync_config_id)
            return {"skipped": "sync disabled"}

        if config.status == "rate_limited" and config.next_sync_at:
            if datetime.now(tz=UTC) < config.next_sync_at:
                if trigger_job_id:
                    await service.mark_job_failed(
                        session, job_id=trigger_job_id, error="rate limited"
                    )
                    await session.commit()
                logger.info("sync_account_job.skipped_rate_limited", sync_config_id=sync_config_id)
                return {"skipped": "rate limited"}

        household_id = config.household_id

        # Look up all accounts linked to this SyncConfig
        acct_result = await session.execute(
            sa.select(Account).where(
                Account.authoritative_sync_config_id == config_id,
                Account.archived_at.is_(None),
            )
        )
        accounts = list(acct_result.scalars().all())

        if not accounts:
            if trigger_job_id:
                await service.mark_job_failed(
                    session, job_id=trigger_job_id, error="no accounts mapped"
                )
                await session.commit()
            logger.info("sync_account_job.no_accounts", sync_config_id=sync_config_id)
            return {"skipped": "no accounts mapped"}

        try:
            creds = service.get_credentials(config, settings.master_key)
        except Exception as exc:
            await service.update_sync_status(
                session,
                config_id=config_id,
                status="error",
                last_error=f"credential decryption failed: {exc}",
            )
            if trigger_job_id:
                await service.mark_job_failed(
                    session, job_id=trigger_job_id, error="credential decryption failed"
                )
            await session.commit()
            logger.error("sync_account_job.credential_error", sync_config_id=sync_config_id)
            return {"error": "credential decryption failed"}

    access_url: str = str(creds.get("access_url", ""))
    if not access_url:
        async with factory() as err_session:
            await service.update_sync_status(
                err_session,
                config_id=config_id,
                status="error",
                last_error="missing access_url in credentials",
            )
            if trigger_job_id:
                await service.mark_job_failed(
                    err_session, job_id=trigger_job_id, error="missing access_url"
                )
            await err_session.commit()
        return {"error": "missing access_url"}

    now = datetime.now(tz=UTC)
    start_date = now - timedelta(days=lookback_days)

    # Increment request counter
    async with factory() as cnt_session:
        request_count = await service.increment_requests_today(cnt_session, config_id=config_id)
        await cnt_session.commit()

    try:
        parsed = await fetch_transactions(access_url, start_date=start_date, end_date=now)
    except Exception as exc:
        error_str = str(exc)
        is_rate_limit = "429" in error_str
        async with factory() as err_session:
            if is_rate_limit:
                next_sync = now + timedelta(hours=_RATE_LIMIT_BACKOFF_HOURS)
                await service.update_sync_status(
                    err_session,
                    config_id=config_id,
                    status="rate_limited",
                    last_error=error_str,
                    next_sync_at=next_sync,
                )
            else:
                await service.update_sync_status(
                    err_session,
                    config_id=config_id,
                    status="error",
                    last_error=error_str,
                )
            if trigger_job_id:
                await service.mark_job_failed(err_session, job_id=trigger_job_id, error=error_str)
            await err_session.commit()
        logger.error("sync_account_job.fetch_failed", error=error_str)
        return {"error": error_str}

    # Route transactions to accounts by simplefin_account_id
    total_imported = 0
    total_duplicate = 0
    total_errors = 0

    async with factory() as session:
        acct_result = await session.execute(
            sa.select(Account).where(
                Account.authoritative_sync_config_id == config_id,
                Account.archived_at.is_(None),
            )
        )
        accounts = list(acct_result.scalars().all())

    for acct in accounts:
        if acct.simplefin_account_id:
            acct_txns = [t for t in parsed if t.source_account_id == str(acct.simplefin_account_id)]
        else:
            acct_txns = parsed

        if not acct_txns:
            continue

        job_row_id = uuid.uuid4()
        async with factory() as session:
            job_row = await service.create_import_job(
                session, household_id=household_id, source=ImportSource.SIMPLEFIN
            )
            job_row_id = job_row.id
            await service.mark_job_running(session, job_id=job_row_id)
            await session.commit()

        pipeline_result = await run_pipeline(
            factory,
            parsed=acct_txns,
            import_job_id=job_row_id,
            household_id=household_id,
            account_id=acct.id,
            source="simplefin",
        )
        total_imported += pipeline_result.imported
        total_duplicate += pipeline_result.duplicate
        total_errors += pipeline_result.errors

    # Update status based on request count
    async with factory() as session:
        new_status = "warning" if request_count >= _REQUESTS_WARNING_THRESHOLD else "active"
        await service.mark_last_synced(session, config_id=config_id)
        await service.update_sync_status(
            session,
            config_id=config_id,
            status=new_status,
            last_error=None,
        )
        if trigger_job_id:
            await service.mark_job_complete(
                session,
                job_id=trigger_job_id,
                imported=total_imported,
                duplicate=total_duplicate,
                errors=total_errors,
            )
        await session.commit()

    logger.info(
        "sync_account_job.complete",
        sync_config_id=sync_config_id,
        imported=total_imported,
        duplicate=total_duplicate,
        errors=total_errors,
    )
    return {
        "sync_config_id": sync_config_id,
        "imported": total_imported,
        "duplicate": total_duplicate,
        "errors": total_errors,
    }


async def sync_account_job(
    ctx: dict[str, Any],
    *,
    sync_config_id: str,
    trigger_import_job_id: str | None = None,
) -> dict[str, Any]:
    """Fetch transactions from SimpleFIN for one SyncConfig and run the pipeline."""
    _ = ctx
    return await _run_simplefin_sync(
        sync_config_id,
        lookback_days=_SIMPLEFIN_LOOKBACK_DAYS,
        trigger_import_job_id=trigger_import_job_id,
    )


async def sync_account_job_initial(ctx: dict[str, Any], *, sync_config_id: str) -> dict[str, Any]:
    """Initial 90-day sync after first account mapping."""
    _ = ctx
    return await _run_simplefin_sync(sync_config_id, lookback_days=_SIMPLEFIN_INITIAL_LOOKBACK_DAYS)


async def process_upload_job(
    ctx: dict[str, Any],
    *,
    import_job_id: str,
    file_bytes_b64: str,
    source: str,
    account_id: str,
    household_id: str,
    csv_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse an uploaded file and run the ingestion pipeline.

    file_bytes_b64: base64-encoded file content (bytes -> base64 in the enqueue call).
    source: "ofx_upload" | "csv_upload" | "statement"
    csv_config: CSV column-mapping config (required when source == "csv_upload").

    Idempotent: stable external_id derivation for CSV prevents double-inserts.
    Bytes are decoded in-memory and discarded; never written to DB.
    """
    _ = ctx
    from app.ingest.parsers.csv import parse_csv
    from app.ingest.parsers.ofx import parse_ofx

    job_id = uuid.UUID(import_job_id)
    hh_id = uuid.UUID(household_id)
    acc_id = uuid.UUID(account_id)

    logger.info("process_upload_job.start", import_job_id=import_job_id, source=source)

    factory = get_session_factory()

    async with factory() as session:
        await service.mark_job_running(session, job_id=job_id)
        await session.commit()

    try:
        file_bytes = base64.b64decode(file_bytes_b64)
    except Exception as exc:
        async with factory() as session:
            await service.mark_job_failed(session, job_id=job_id, error=f"base64 decode: {exc}")
            await session.commit()
        return {"error": "base64 decode failed"}

    try:
        if source in ("ofx_upload", "statement"):
            parsed = parse_ofx(file_bytes)
        elif source == "csv_upload":
            if not csv_config:
                raise ValueError("csv_config required for csv_upload")
            parsed = parse_csv(file_bytes, csv_config)
        else:
            raise ValueError(f"unknown source: {source!r}")
    except Exception as exc:
        async with factory() as session:
            await service.mark_job_failed(session, job_id=job_id, error=f"parse error: {exc}")
            await session.commit()
        logger.error("process_upload_job.parse_failed", error=str(exc))
        return {"error": str(exc)}

    pipeline_result = await run_pipeline(
        factory,
        parsed=parsed,
        import_job_id=job_id,
        household_id=hh_id,
        account_id=acc_id,
        source=source,
    )

    logger.info(
        "process_upload_job.complete",
        import_job_id=import_job_id,
        imported=pipeline_result.imported,
        duplicate=pipeline_result.duplicate,
        errors=pipeline_result.errors,
    )
    return {
        "import_job_id": import_job_id,
        "imported": pipeline_result.imported,
        "duplicate": pipeline_result.duplicate,
        "errors": pipeline_result.errors,
    }


async def schedule_syncs_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Hourly ARQ cron: enqueue sync_account_job for all SyncConfigs that are due.

    A config is due when:
      - sync_enabled is True and status is not "disabled"
      - rate_limited configs are skipped unless next_sync_at has passed
      - last_synced_at is None (never synced) OR older than sync_interval_hours
    """
    import arq

    from app.worker.settings import get_redis_settings

    _ = ctx
    now = datetime.now(tz=UTC)
    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            sa.select(SyncConfig).where(
                SyncConfig.archived_at.is_(None),
                SyncConfig.sync_enabled.is_(True),
                SyncConfig.status != "disabled",
            )
        )
        all_configs = list(result.scalars().all())

    configs_due: list[SyncConfig] = []
    for c in all_configs:
        if c.status == "rate_limited":
            if c.next_sync_at is None or now < c.next_sync_at:
                continue
        if c.last_synced_at is None:
            configs_due.append(c)
            continue
        due_at = c.last_synced_at + timedelta(hours=c.sync_interval_hours)
        if now >= due_at:
            configs_due.append(c)

    logger.info("schedule_syncs_job.start", configs_due=len(configs_due))

    pool = await arq.create_pool(get_redis_settings())
    enqueued = 0
    try:
        for c in configs_due:
            job = await pool.enqueue_job("sync_account_job", sync_config_id=str(c.id))
            if job is not None:
                enqueued += 1
    finally:
        await pool.aclose()

    skipped = len(configs_due) - enqueued
    logger.info("schedule_syncs_job.complete", enqueued=enqueued, skipped=skipped)
    return {"configs_due": len(configs_due), "enqueued": enqueued}


async def reset_requests_today_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Daily ARQ cron: reset requests_today=0 on all SyncConfigs where date has changed.

    Scheduled via worker-slow cron at midnight UTC.
    """
    _ = ctx
    from datetime import date

    today = date.today()
    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            sa.update(SyncConfig)
            .where(
                SyncConfig.archived_at.is_(None),
                sa.or_(
                    SyncConfig.requests_today_reset_at.is_(None),
                    SyncConfig.requests_today_reset_at < today,
                ),
            )
            .values(requests_today=0, requests_today_reset_at=today)
        )
        await session.commit()
        updated: int = result.rowcount  # type: ignore[assignment]

    logger.info("reset_requests_today_job.complete", updated=updated)
    return {"updated": updated}
