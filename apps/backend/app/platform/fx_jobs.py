"""ARQ background jobs for FX rate management.

Slow pool jobs:
  fetch_daily_rates_job(household_id)         -- fetch Frankfurter rates for all
                                                 foreign currencies in the household
  recompute_fx_conversions_job(household_id)  -- triggered by home currency change;
                                                 invalidates and rebuilds actuals
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import sqlalchemy as sa
import structlog

from app.database import get_session_factory
from app.platform.fx import fetch_and_store_rates

logger = structlog.get_logger(__name__)


async def fetch_daily_rates_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Fetch today's FX rates for all foreign-currency accounts in the household.

    Never raises -- uses fallback rates if Frankfurter unavailable.
    Scheduled daily at 9am UTC per household.
    """
    _ = ctx
    hid = uuid.UUID(household_id)
    today = date.today()
    factory = get_session_factory()

    async with factory() as session:
        # Get household home_currency via raw SQL to avoid cross-module import
        hh_row = await session.execute(
            sa.text(
                "SELECT home_currency FROM households_household "
                "WHERE id = :hid AND archived_at IS NULL"
            ).bindparams(hid=str(hid))
        )
        hh = hh_row.fetchone()
        if hh is None:
            logger.warning("fx_daily.household_not_found", household_id=household_id)
            return {"skipped": True}

        home_currency: str = hh[0]

        # Distinct foreign currencies from accounts
        acc_rows = await session.execute(
            sa.text(
                "SELECT DISTINCT currency FROM accounts_account "
                "WHERE household_id = :hid AND archived_at IS NULL "
                "AND currency != :home"
            ).bindparams(hid=str(hid), home=home_currency)
        )
        foreign_currencies = [row[0] for row in acc_rows.fetchall()]

        if not foreign_currencies:
            logger.info("fx_daily.no_foreign_currencies", household_id=household_id)
            return {"home_currency": home_currency, "currencies_fetched": 0}

        await fetch_and_store_rates(
            base_currency=home_currency,
            target_currencies=foreign_currencies,
            rate_date=today,
            session=session,
        )
        await session.commit()

    logger.info(
        "fx_daily.complete",
        household_id=household_id,
        currencies=foreign_currencies,
        date=str(today),
    )
    return {
        "home_currency": home_currency,
        "currencies_fetched": len(foreign_currencies),
        "date": str(today),
    }


async def recompute_fx_conversions_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Recompute all FX-dependent aggregates after a home currency change.

    Idempotent -- safe to re-run if it fails partway through.
    Steps:
      1. Delete BudgetPeriodActual rows (will recompute on next access via compute_actuals).
      2. Delete GoalSnapshot rows (will recompute on next access via compute_burn_up).
      3. Invalidate ProjectionRun cache.
      4. Re-run compute_actuals for all active budgets.
      5. Re-run compute_burn_up for all active goals.
      6. Emit SSE fx_recompute_complete to household members.
    """
    _ = ctx
    hid = uuid.UUID(household_id)
    factory = get_session_factory()

    async with factory() as session:
        # 1. Clear BudgetPeriodActual (derived cache -- safe to delete)
        await session.execute(
            sa.text(
                "DELETE FROM budgets_period_actual pa "
                "USING budgets_budget_line bl "
                "WHERE pa.budget_line_id = bl.id "
                "AND bl.household_id = :hid"
            ).bindparams(hid=str(hid))
        )

        # 2. Clear GoalSnapshot
        await session.execute(
            sa.text(
                "DELETE FROM goals_snapshot gs "
                "USING goals_goal g "
                "WHERE gs.goal_id = g.id AND g.household_id = :hid"
            ).bindparams(hid=str(hid))
        )

        # 3. Invalidate ProjectionRun cache (delete non-scenario runs)
        await session.execute(
            sa.text("DELETE FROM projections_projection_run WHERE household_id = :hid").bindparams(
                hid=str(hid)
            )
        )

        await session.commit()

        # 4. Re-run compute_actuals for all active budget groups
        budget_rows = await session.execute(
            sa.text(
                "SELECT DISTINCT budget_group_id FROM budgets_budget "
                "WHERE household_id = :hid AND archived_at IS NULL AND effective_to IS NULL"
            ).bindparams(hid=str(hid))
        )
        budget_group_ids = [row[0] for row in budget_rows.fetchall()]

        for bgid in budget_group_ids:
            try:
                import datetime as _dt

                from app.budgets.service import compute_actuals, resolve_period
                from app.budgets.service import get_budget as get_budget_svc

                today = _dt.date.today()
                budget = await get_budget_svc(
                    session, budget_group_id=uuid.UUID(str(bgid)), household_id=hid
                )
                period_start, period_end = resolve_period(budget, today)
                await compute_actuals(
                    session,
                    budget_group_id=uuid.UUID(str(bgid)),
                    household_id=hid,
                    period_start=period_start,
                    period_end=period_end,
                )
                await session.commit()
            except Exception as exc:
                logger.warning(
                    "fx_recompute.budget_failed",
                    budget_group_id=str(bgid),
                    error=str(exc),
                )
                await session.rollback()

        # 5. Re-run compute_burn_up for all active goals
        goal_rows = await session.execute(
            sa.text(
                "SELECT id FROM goals_goal "
                "WHERE household_id = :hid AND archived_at IS NULL AND status = 'active'"
            ).bindparams(hid=str(hid))
        )
        goal_ids = [row[0] for row in goal_rows.fetchall()]

        for gid in goal_ids:
            try:
                from app.goals.service import compute_burn_up

                await compute_burn_up(session, goal_id=uuid.UUID(str(gid)), household_id=hid)
                await session.commit()
            except Exception as exc:
                logger.warning(
                    "fx_recompute.goal_failed",
                    goal_id=str(gid),
                    error=str(exc),
                )
                await session.rollback()

        # 6. Emit SSE event to household members
        try:
            member_rows = await session.execute(
                sa.text(
                    "SELECT user_id FROM households_membership "
                    "WHERE household_id = :hid AND archived_at IS NULL"
                ).bindparams(hid=str(hid))
            )
            member_ids = [row[0] for row in member_rows.fetchall()]

            from app.households.sse import get_sse_manager

            mgr = get_sse_manager()
            for mid in member_ids:
                await mgr.send_to_user(
                    uuid.UUID(str(mid)),
                    "fx_recompute_complete",
                    {"household_id": household_id},
                )
        except Exception as exc:
            logger.warning("fx_recompute.sse_failed", error=str(exc))

    logger.info(
        "fx_recompute.complete",
        household_id=household_id,
        budgets=len(budget_group_ids),
        goals=len(goal_ids),
    )
    return {
        "household_id": household_id,
        "budgets_recomputed": len(budget_group_ids),
        "goals_recomputed": len(goal_ids),
    }
