"""ARQ background jobs for the goals module.

goal_status_recalc_job -> worker-slow
  Daily sweep: compute_burn_up + check_completion + check_minimum_balance
  for all active goals in a household.
  Also triggered when a new contribution is logged.
  Idempotent: safe to run twice.
"""

from datetime import date
from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def goal_status_recalc_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Recompute burn-up and apply checks for all active goals in a household."""
    _ = ctx
    import uuid

    from app.goals import service
    from app.goals.enums import GoalStatus, GoalType

    hh_id = uuid.UUID(household_id)
    logger.info("goal_status_recalc.start", household_id=household_id)

    factory = get_session_factory()
    processed = 0
    errors = 0

    async with factory() as session:
        try:
            goals = await service.list_goals(session, household_id=hh_id, status=GoalStatus.ACTIVE)
        except Exception as exc:
            logger.error("goal_status_recalc.list_failed", error=str(exc))
            return {"household_id": household_id, "status": "error", "error": str(exc)}

        as_of = date.today()

        for goal in goals:
            try:
                await service.compute_burn_up(
                    session, goal_id=goal.id, household_id=hh_id, as_of_date=as_of
                )
                await service.check_completion(session, goal_id=goal.id, household_id=hh_id)
                if goal.goal_type == str(GoalType.MINIMUM_BALANCE):
                    await service.check_minimum_balance(
                        session, goal_id=goal.id, household_id=hh_id
                    )
                await session.commit()
                processed += 1
            except Exception as exc:
                await session.rollback()
                logger.warning(
                    "goal_status_recalc.goal_failed",
                    goal_id=str(goal.id),
                    error=str(exc),
                )
                errors += 1

    logger.info(
        "goal_status_recalc.complete",
        household_id=household_id,
        processed=processed,
        errors=errors,
    )
    return {
        "household_id": household_id,
        "processed": processed,
        "errors": errors,
        "status": "ok",
    }
