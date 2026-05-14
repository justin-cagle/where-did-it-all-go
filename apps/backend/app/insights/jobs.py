"""ARQ background jobs for the insights module.

Jobs registered in app.worker.slow (worker-slow pool — long jobs, low concurrency).

generate_insights_job: run anomaly + pattern generators for a household.
Rate-limited: skips if last successful run was < 6 hours ago.
Triggered by ingest pipeline after transactions are imported.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
import structlog

from app.database import get_session_factory
from app.insights.models import InsightAuditLog

logger = structlog.get_logger(__name__)

_RATE_LIMIT_HOURS = 6


async def generate_insights_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Generate anomaly and pattern insights for a household.

    Idempotent: re-running after a crash re-generates insights (no harm).
    Rate-limited: skip if a successful run completed within the last 6 hours.
    """
    _ = ctx
    from app.config import get_settings
    from app.insights import service

    hh_id = uuid.UUID(household_id)
    logger.info("generate_insights_job.start", household_id=household_id)

    factory = get_session_factory()
    settings = get_settings()

    async with factory() as session:
        # Rate-limit check: any successful insight in last 6h?
        cutoff = datetime.now(tz=UTC) - timedelta(hours=_RATE_LIMIT_HOURS)
        result = await session.execute(
            sa.select(InsightAuditLog)
            .where(
                InsightAuditLog.household_id == hh_id,
                InsightAuditLog.success.is_(True),
                InsightAuditLog.created_at >= cutoff,
            )
            .limit(1)
        )
        recent = result.scalar_one_or_none()
        if recent is not None:
            logger.info(
                "generate_insights_job.rate_limited",
                household_id=household_id,
                last_run=str(recent.created_at),
            )
            return {"skipped": "rate_limited", "last_run": str(recent.created_at)}

    async with factory() as session:
        try:
            await service.generate_anomaly_insights(session, hh_id, settings.master_key)
            await session.commit()
        except Exception as exc:
            logger.error(
                "generate_insights_job.anomaly_error",
                household_id=household_id,
                error=str(exc),
            )
            await session.rollback()

    async with factory() as session:
        try:
            await service.generate_pattern_insights(session, hh_id, settings.master_key)
            await session.commit()
        except Exception as exc:
            logger.error(
                "generate_insights_job.pattern_error",
                household_id=household_id,
                error=str(exc),
            )
            await session.rollback()

    logger.info("generate_insights_job.complete", household_id=household_id)
    return {"status": "complete", "household_id": household_id}
