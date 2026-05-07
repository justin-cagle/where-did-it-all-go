"""ARQ background jobs for the debts module.

recompute_debt_schedule_job -> worker-slow
  Triggered when DebtBalance changes (payment reconciled, APR updated).
  Idempotent: safe to run twice.
"""

import uuid
from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def recompute_debt_schedule_job(
    ctx: dict[str, Any],
    *,
    plan_group_id: str,
    household_id: str,
) -> dict[str, Any]:
    """Recompute debt schedule for an active plan.

    Triggered when balance data changes. Idempotent.
    """
    _ = ctx
    from app.debts import service

    pg_id = uuid.UUID(plan_group_id)
    hh_id = uuid.UUID(household_id)
    logger.info("debt_schedule.recompute.start", plan_group_id=plan_group_id)

    factory = get_session_factory()
    async with factory() as session:
        try:
            summary = await service.compute_schedule(
                session, plan_group_id=pg_id, household_id=hh_id
            )
            await session.commit()
        except service.NotFoundError:
            logger.warning("debt_schedule.recompute.plan_not_found", plan_group_id=plan_group_id)
            return {"plan_group_id": plan_group_id, "status": "not_found"}

    logger.info(
        "debt_schedule.recompute.complete",
        plan_group_id=plan_group_id,
        months=summary.months_to_payoff,
    )
    return {
        "plan_group_id": plan_group_id,
        "months_to_payoff": summary.months_to_payoff,
        "status": "ok",
    }
