"""ARQ background jobs for the budgets module.

budget_period_close_job -> worker-slow (daily sweep per household)
  Runs at period boundary: compute_actuals for closing period, apply rollovers.
  Idempotent: safe to call daily even when no period boundary has crossed.
"""

import uuid
from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def budget_period_close_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Close any periods that ended yesterday for the household and apply rollovers.

    Scheduled daily per household by the platform scheduler.
    Idempotent: if no period boundary crossed yesterday, returns skipped=n, closed=0.
    """
    _ = ctx
    from app.budgets import service

    hh_id = uuid.UUID(household_id)
    logger.info("budget_period_close.start", household_id=household_id)

    factory = get_session_factory()

    async with factory() as session:
        result = await service.period_close(session, household_id=hh_id)
        await session.commit()

    logger.info(
        "budget_period_close.complete",
        household_id=household_id,
        closed=result["closed"],
        skipped=result["skipped"],
    )
    return {"household_id": household_id, **result}
