"""ARQ background jobs for the projections module.

invalidate_projection_cache_job -> worker-fast
  Expires all cached ProjectionRuns for a household.
  Triggered by domain events: new transaction, budget edit, debt payment,
  goal contribution, recurrence change.
  Just calls invalidate_cache() -- recompute is on-demand.

cleanup_transient_scenarios_job -> worker-slow (daily)
  Deletes unsaved scenarios older than 24 hours.
"""

from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def invalidate_projection_cache_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Expire all cached projection runs for a household."""
    _ = ctx
    import uuid

    from app.projections import service

    hh_id = uuid.UUID(household_id)
    logger.info("projection.cache_invalidate.start", household_id=household_id)

    factory = get_session_factory()
    async with factory() as session:
        try:
            await service.invalidate_cache(session, household_id=hh_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "projection.cache_invalidate.failed",
                household_id=household_id,
                error=str(exc),
            )
            return {"household_id": household_id, "status": "error", "error": str(exc)}

    logger.info("projection.cache_invalidate.done", household_id=household_id)
    return {"household_id": household_id, "status": "ok"}


async def cleanup_transient_scenarios_job(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Delete all transient (unsaved) scenarios older than 24 hours across all households."""
    _ = ctx
    import sqlalchemy as sa

    from app.households.models import Household
    from app.projections import service

    logger.info("projection.cleanup_transient.start")

    factory = get_session_factory()
    total_deleted = 0

    async with factory() as session:
        result = await session.execute(sa.select(Household.id))
        household_ids = [row[0] for row in result.all()]

    for hh_id in household_ids:
        async with factory() as session:
            try:
                deleted = await service.cleanup_transient_scenarios(session, household_id=hh_id)
                await session.commit()
                total_deleted += deleted
            except Exception as exc:
                await session.rollback()
                logger.warning(
                    "projection.cleanup_transient.household_failed",
                    household_id=str(hh_id),
                    error=str(exc),
                )

    logger.info("projection.cleanup_transient.done", deleted=total_deleted)
    return {"deleted": total_deleted, "status": "ok"}
