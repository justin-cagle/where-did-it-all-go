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

# Hard limit: stop fetching SimpleFIN data older than this many days per run
_SIMPLEFIN_LOOKBACK_DAYS = 30


async def sync_account_job(ctx: dict[str, Any], *, sync_config_id: str) -> dict[str, Any]:
    """Fetch transactions from SimpleFIN for one SyncConfig and run the pipeline.

    Idempotent: same transactions are detected as duplicates on re-run.
    Structured start/finish/error events emitted via structlog.
    """
    _ = ctx  # ARQ context not needed for this job
    from app.config import get_settings
    from app.ingest.parsers.simplefin import fetch_transactions

    config_id = uuid.UUID(sync_config_id)
    logger.info("sync_account_job.start", sync_config_id=sync_config_id)

    factory = get_session_factory()
    settings = get_settings()

    # Load the SyncConfig directly (job runs as system; no user context)
    async with factory() as session:
        result = await session.execute(sa.select(SyncConfig).where(SyncConfig.id == config_id))
        config = result.scalar_one_or_none()
        if config is None:
            logger.error("sync_account_job.config_not_found", sync_config_id=sync_config_id)
            return {"error": "sync config not found"}

        if not config.sync_enabled:
            logger.info("sync_account_job.skipped_disabled", sync_config_id=sync_config_id)
            return {"skipped": "sync disabled"}

        household_id = config.household_id
        account_id = config.account_id

        # Create ImportJob
        job_row = await service.create_import_job(
            session, household_id=household_id, source=ImportSource.SIMPLEFIN
        )
        import_job_id = job_row.id
        await service.mark_job_running(session, job_id=import_job_id)
        await session.commit()

        try:
            creds = service.get_credentials(config, settings.master_key)
        except Exception as exc:
            async with factory() as err_session:
                await service.mark_job_failed(err_session, job_id=import_job_id, error=str(exc))
                await err_session.commit()
            logger.error("sync_account_job.credential_error", sync_config_id=sync_config_id)
            return {"error": "credential decryption failed"}

    access_url: str = creds.get("access_url", "")
    if not access_url:
        async with factory() as err_session:
            await service.mark_job_failed(
                err_session, job_id=import_job_id, error="missing access_url in credentials"
            )
            await err_session.commit()
        return {"error": "missing access_url"}

    now = datetime.now(tz=UTC)
    start_date = now - timedelta(days=_SIMPLEFIN_LOOKBACK_DAYS)

    try:
        parsed = await fetch_transactions(access_url, start_date=start_date, end_date=now)
    except Exception as exc:
        async with factory() as err_session:
            await service.mark_job_failed(
                err_session, job_id=import_job_id, error=f"SimpleFIN fetch failed: {exc}"
            )
            await err_session.commit()
        logger.error("sync_account_job.fetch_failed", error=str(exc))
        return {"error": str(exc)}

    pipeline_result = await run_pipeline(
        factory,
        parsed=parsed,
        import_job_id=import_job_id,
        household_id=household_id,
        account_id=account_id,
        source="simplefin",
    )

    async with factory() as session:
        await service.mark_last_synced(session, config_id=config_id)
        await session.commit()

    logger.info(
        "sync_account_job.complete",
        sync_config_id=sync_config_id,
        imported=pipeline_result.imported,
        duplicate=pipeline_result.duplicate,
        errors=pipeline_result.errors,
    )
    return {
        "import_job_id": str(import_job_id),
        "imported": pipeline_result.imported,
        "duplicate": pipeline_result.duplicate,
        "errors": pipeline_result.errors,
    }


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

    file_bytes_b64: base64-encoded file content (bytes → base64 in the enqueue call).
    source: "ofx_upload" | "csv_upload" | "statement"
    csv_config: CSV column-mapping config (required when source == "csv_upload").

    Idempotent: stable external_id derivation for CSV prevents double-inserts.
    Bytes are decoded in-memory and discarded; never written to DB.
    """
    _ = ctx  # ARQ context not needed for this job
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
