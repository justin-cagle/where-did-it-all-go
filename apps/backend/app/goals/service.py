"""Goals service layer.

Owns goal CRUD, funding sources, contribution logging, burn-up computation,
completion policy enforcement, and Recommendation emission.

Never writes to budgets, debts, or transactions tables directly.
Cross-module data access:
  - Account balance:    app.accounts.service.get_account()
  - Transaction spend:  app.transactions.service.get_allocations_in_range()
  - Debt payoff data:   app.debts.service.get_summary()

Public interface:
  create_goal(...)                                           -> Goal
  get_goal(goal_id, household_id)                           -> Goal
  update_goal(...)                                          -> Goal
  archive_goal(...)                                         -> Goal
  list_goals(household_id, status)                          -> list[Goal]
  pause_goal(goal_id, household_id, actor_id)              -> Goal
  resume_goal(goal_id, household_id, actor_id)             -> Goal
  create_funding_source(...)                                -> GoalFundingSource
  list_funding_sources(goal_id, household_id)              -> list[GoalFundingSource]
  delete_funding_source(source_id, goal_id, household_id)  -> None
  log_contribution(...)                                     -> GoalContribution
  get_contributions(goal_id, household_id)                 -> list[GoalContribution]
  get_per_user_contributions(goal_id, household_id)        -> PerUserBreakdown
  scan_tag_contributions(household_id)                     -> int
  compute_burn_up(goal_id, household_id, as_of_date)       -> GoalSnapshot
  get_latest_snapshot(goal_id, household_id)               -> GoalSnapshot
  list_snapshots(goal_id, household_id)                    -> list[GoalSnapshot]
  check_completion(goal_id, household_id, actor_id)        -> None
  check_minimum_balance(goal_id, household_id)             -> None
  check_category_reduction(goal_id, household_id,
    period_start, period_end)                              -> None
  get_all_status(household_id, as_of_date)                 -> list[GoalSnapshot]
  manual_complete(goal_id, household_id, actor_id)         -> None
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

import app.accounts.service as accounts_svc
import app.recommendations.service as rec_svc
import app.transactions.service as txn_svc
from app.audit.models import ActorType, AuditEvent, AuditOperation
from app.goals.enums import (
    BurnUpStatus,
    CompletionPolicy,
    ContributionType,
    FundingSourceType,
    FundingStrategy,
    GoalStatus,
    GoalType,
)
from app.goals.models import Goal, GoalContribution, GoalFundingSource, GoalSnapshot
from app.platform.time import utcnow
from app.recommendations.enums import RecommendationSource

logger = structlog.get_logger(__name__)

_CENT = Decimal("0.01")
_DAYS_TRAILING = 30


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a state constraint."""


class ValidationError(Exception):
    """Domain invariant violated."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class UserContributionTotal:
    attributed_to_user_id: uuid.UUID | None
    total: Decimal
    currency: str


@dataclass
class PerUserBreakdown:
    contributions: list[GoalContribution]
    per_user: list[UserContributionTotal]
    household_total: Decimal
    currency: str


# ---------------------------------------------------------------------------
# Pure burn-up helpers
# ---------------------------------------------------------------------------


def _derive_burn_up_status(
    gap_pct: Decimal,
    thresholds: dict[str, Any] | None = None,
) -> BurnUpStatus:
    """Classify burn-up status from gap_pct (gap / target * 100).

    Positive gap_pct = behind. Negative = ahead.
    Default thresholds (configurable via goal metadata):
      ahead:    gap_pct < -5
      on_track: -5 <= gap_pct <= 5
      behind:   5 < gap_pct <= 15
      at_risk:  15 < gap_pct <= 30
      off_track: gap_pct > 30
    """
    t = thresholds or {}
    ahead_threshold = Decimal(str(t.get("ahead_threshold", "-5")))
    on_track_threshold = Decimal(str(t.get("on_track_threshold", "5")))
    behind_threshold = Decimal(str(t.get("behind_threshold", "15")))
    at_risk_threshold = Decimal(str(t.get("at_risk_threshold", "30")))

    if gap_pct < ahead_threshold:
        return BurnUpStatus.AHEAD
    if gap_pct <= on_track_threshold:
        return BurnUpStatus.ON_TRACK
    if gap_pct <= behind_threshold:
        return BurnUpStatus.BEHIND
    if gap_pct <= at_risk_threshold:
        return BurnUpStatus.AT_RISK
    return BurnUpStatus.OFF_TRACK


def compute_burn_up_pure(
    *,
    target_amount: Decimal,
    start_date: date,
    target_date: date | None,
    as_of_date: date,
    cumulative_actual: Decimal,
    trailing_30d_actual: Decimal,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure burn-up computation (no DB). Returns a dict of snapshot fields.

    When target_date is None (e.g. minimum_balance, no end date), pace-based
    fields are set to zero and status is derived from progress_pct only.
    """
    zero = Decimal("0")

    # required_pace: monthly rate to close from start to target_date
    if target_date is not None and target_date > start_date:
        total_days = (target_date - start_date).days
        days_elapsed = max(0, (as_of_date - start_date).days)

        remaining = (target_amount - cumulative_actual).quantize(_CENT, ROUND_HALF_UP)
        required_pace_daily = (
            (target_amount / Decimal(total_days)).quantize(_CENT, ROUND_HALF_UP)
            if total_days > 0
            else zero
        )
        required_pace = (required_pace_daily * Decimal("30.4375")).quantize(_CENT, ROUND_HALF_UP)

        cumulative_expected = (required_pace_daily * Decimal(days_elapsed)).quantize(
            _CENT, ROUND_HALF_UP
        )

        # projected_completion_date: extrapolate actual_pace
        actual_pace_daily = (trailing_30d_actual / Decimal("30.4375")).quantize(
            _CENT, ROUND_HALF_UP
        )
        if actual_pace_daily > zero and remaining > zero:
            days_to_complete = int(
                min(
                    (remaining / actual_pace_daily).to_integral_value(ROUND_HALF_UP),
                    Decimal("999999"),  # cap to keep date within year 9999
                )
            )
            try:
                projected_completion_date: date | None = as_of_date + timedelta(
                    days=days_to_complete
                )
            except OverflowError:
                projected_completion_date = None
        elif remaining <= zero:
            projected_completion_date = as_of_date
        else:
            projected_completion_date = None

        gap_to_close = (cumulative_expected - cumulative_actual).quantize(_CENT, ROUND_HALF_UP)

        if target_amount > zero:
            gap_pct = (gap_to_close / target_amount * Decimal("100")).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
        else:
            gap_pct = zero
    else:
        required_pace = zero
        cumulative_expected = zero
        projected_completion_date = None
        gap_to_close = zero
        gap_pct = zero

    if target_amount > zero:
        progress_pct = (cumulative_actual / target_amount * Decimal("100")).quantize(
            Decimal("0.0001"), ROUND_HALF_UP
        )
    else:
        progress_pct = Decimal("0.0000")

    status = _derive_burn_up_status(gap_pct, thresholds)

    return {
        "cumulative_expected": cumulative_expected,
        "required_pace": required_pace,
        "actual_pace": trailing_30d_actual,
        "projected_completion_date": projected_completion_date,
        "gap_to_close": gap_to_close,
        "progress_pct": progress_pct,
        "burn_up_status": str(status),
    }


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


async def create_goal(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    goal_type: GoalType,
    description: str | None = None,
    target_amount: Decimal | None = None,
    currency: str = "USD",
    target_date: date | None = None,
    funding_strategy: FundingStrategy = FundingStrategy.VIRTUAL_ALLOCATION,
    completion_policy: CompletionPolicy = CompletionPolicy.PROMPT_ON_COMPLETE,
    auto_extend_amount: Decimal | None = None,
    owner_id: uuid.UUID | None = None,
    linked_debt_plan_id: uuid.UUID | None = None,
    linked_category_id: uuid.UUID | None = None,
    minimum_balance_threshold: Decimal | None = None,
    metadata: dict[str, Any] | None = None,
) -> Goal:
    """Create a new goal for a household."""
    goal = Goal(
        household_id=household_id,
        name=name,
        description=description,
        goal_type=str(goal_type),
        status=str(GoalStatus.ACTIVE),
        target_amount=target_amount,
        currency=currency.upper(),
        target_date=target_date,
        funding_strategy=str(funding_strategy),
        completion_policy=str(completion_policy),
        auto_extend_amount=auto_extend_amount,
        owner_id=owner_id,
        linked_debt_plan_id=linked_debt_plan_id,
        linked_category_id=linked_category_id,
        minimum_balance_threshold=minimum_balance_threshold,
        metadata_=metadata or {},
    )
    session.add(goal)
    await session.flush()

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal.id,
            operation=str(AuditOperation.CREATE),
            delta=[{"op": "add", "path": "/name", "value": name}],
        )
    )
    await session.flush()
    logger.info("goal.created", goal_id=str(goal.id), household_id=str(household_id))
    return goal


async def get_goal(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> Goal:
    """Return goal scoped to household. Raises NotFoundError if absent."""
    result = await session.execute(
        sa.select(Goal).where(
            Goal.id == goal_id,
            Goal.household_id == household_id,
            Goal.archived_at.is_(None),
        )
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise NotFoundError("goal not found")
    return goal


async def update_goal(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    **kwargs: Any,  # noqa: ANN401
) -> Goal:
    """Update mutable fields on a goal."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)

    updatable = {
        "name",
        "description",
        "target_amount",
        "currency",
        "target_date",
        "funding_strategy",
        "completion_policy",
        "auto_extend_amount",
        "owner_id",
        "linked_debt_plan_id",
        "linked_category_id",
        "minimum_balance_threshold",
        "metadata_",
    }
    delta = []
    for k, v in kwargs.items():
        if k not in updatable or v is None:
            continue
        old = getattr(goal, k)
        if old != v:
            delta.append({"op": "replace", "path": f"/{k}", "value": str(v)})
            if k == "currency" and isinstance(v, str):
                setattr(goal, k, v.upper())
            elif k in ("funding_strategy", "completion_policy"):
                setattr(goal, k, str(v))
            else:
                setattr(goal, k, v)

    await session.flush()

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.UPDATE),
            delta=delta,
        )
    )
    await session.flush()
    logger.info("goal.updated", goal_id=str(goal_id))
    return goal


async def archive_goal(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Goal:
    """Soft-delete a goal."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    now = utcnow()
    goal.archived_at = now
    goal.archived_by = actor_id
    goal.status = str(GoalStatus.ARCHIVED)
    await session.flush()

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.ARCHIVE),
            delta=[],
        )
    )
    await session.flush()
    logger.info("goal.archived", goal_id=str(goal_id))
    return goal


async def list_goals(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    status: GoalStatus | None = None,
) -> list[Goal]:
    """Return goals for a household, optionally filtered by status."""
    stmt = sa.select(Goal).where(
        Goal.household_id == household_id,
        Goal.archived_at.is_(None),
    )
    if status is not None:
        stmt = stmt.where(Goal.status == str(status))
    stmt = stmt.order_by(Goal.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def pause_goal(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Goal:
    """Pause an active goal."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    if goal.status != str(GoalStatus.ACTIVE):
        raise ConflictError(f"goal is {goal.status}, cannot pause")
    goal.status = str(GoalStatus.PAUSED)
    await session.flush()
    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.UPDATE),
            delta=[{"op": "replace", "path": "/status", "value": "paused"}],
        )
    )
    await session.flush()
    return goal


async def resume_goal(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Goal:
    """Resume a paused goal."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    if goal.status != str(GoalStatus.PAUSED):
        raise ConflictError(f"goal is {goal.status}, cannot resume")
    goal.status = str(GoalStatus.ACTIVE)
    await session.flush()
    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.UPDATE),
            delta=[{"op": "replace", "path": "/status", "value": "active"}],
        )
    )
    await session.flush()
    return goal


# ---------------------------------------------------------------------------
# Funding sources
# ---------------------------------------------------------------------------


async def create_funding_source(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    source_type: FundingSourceType,
    source_id: uuid.UUID | None = None,
    attributed_to_user_id: uuid.UUID | None = None,
) -> GoalFundingSource:
    """Add a funding source to a goal."""
    await get_goal(session, goal_id=goal_id, household_id=household_id)
    fs = GoalFundingSource(
        goal_id=goal_id,
        household_id=household_id,
        source_type=str(source_type),
        source_id=source_id,
        attributed_to_user_id=attributed_to_user_id,
    )
    session.add(fs)
    await session.flush()
    return fs


async def list_funding_sources(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[GoalFundingSource]:
    """Return all funding sources for a goal."""
    result = await session.execute(
        sa.select(GoalFundingSource).where(
            GoalFundingSource.goal_id == goal_id,
            GoalFundingSource.household_id == household_id,
        )
    )
    return list(result.scalars().all())


async def delete_funding_source(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> None:
    """Remove a funding source from a goal."""
    result = await session.execute(
        sa.select(GoalFundingSource).where(
            GoalFundingSource.id == source_id,
            GoalFundingSource.goal_id == goal_id,
            GoalFundingSource.household_id == household_id,
        )
    )
    fs = result.scalar_one_or_none()
    if fs is None:
        raise NotFoundError("funding source not found")
    await session.delete(fs)
    await session.flush()


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------


async def log_contribution(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    amount: Decimal,
    currency: str = "USD",
    contributed_at: date,
    contribution_type: ContributionType = ContributionType.MANUAL,
    transaction_id: uuid.UUID | None = None,
    attributed_to_user_id: uuid.UUID | None = None,
    note: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> GoalContribution:
    """Record a contribution against a goal.

    For tag_driven contributions: idempotent on (goal_id, transaction_id).
    """
    await get_goal(session, goal_id=goal_id, household_id=household_id)

    if transaction_id is not None:
        dup = await session.execute(
            sa.select(GoalContribution).where(
                GoalContribution.goal_id == goal_id,
                GoalContribution.transaction_id == transaction_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError("contribution already logged for this transaction")

    contrib = GoalContribution(
        goal_id=goal_id,
        household_id=household_id,
        amount=amount,
        currency=currency.upper(),
        contributed_at=contributed_at,
        contribution_type=str(contribution_type),
        transaction_id=transaction_id,
        attributed_to_user_id=attributed_to_user_id,
        note=note,
    )
    session.add(contrib)
    await session.flush()

    if actor_id is not None:
        session.add(
            AuditEvent(
                actor_type=str(ActorType.USER),
                actor_id=actor_id,
                actor_source="user_action",
                household_id=household_id,
                entity_type="goal_contribution",
                entity_id=contrib.id,
                operation=str(AuditOperation.CREATE),
                delta=[
                    {"op": "add", "path": "/amount", "value": str(amount)},
                    {"op": "add", "path": "/goal_id", "value": str(goal_id)},
                ],
            )
        )
        await session.flush()

    logger.info(
        "goal.contribution.logged",
        goal_id=str(goal_id),
        amount=str(amount),
        type=str(contribution_type),
    )
    return contrib


async def get_contributions(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[GoalContribution]:
    """Return all contributions for a goal ordered by date."""
    result = await session.execute(
        sa.select(GoalContribution)
        .where(
            GoalContribution.goal_id == goal_id,
            GoalContribution.household_id == household_id,
        )
        .order_by(GoalContribution.contributed_at)
    )
    return list(result.scalars().all())


async def get_per_user_contributions(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> PerUserBreakdown:
    """Return contributions broken down by attributed user."""
    contribs = await get_contributions(session, goal_id=goal_id, household_id=household_id)
    if not contribs:
        currency = "USD"
        result = await session.execute(sa.select(Goal.currency).where(Goal.id == goal_id))
        row = result.scalar_one_or_none()
        if row:
            currency = row
        return PerUserBreakdown(
            contributions=[], per_user=[], household_total=Decimal("0"), currency=currency
        )

    currency = contribs[0].currency
    totals: dict[uuid.UUID | None, Decimal] = {}
    for c in contribs:
        key = c.attributed_to_user_id
        totals[key] = totals.get(key, Decimal("0")) + c.amount

    per_user = [
        UserContributionTotal(attributed_to_user_id=uid, total=total, currency=currency)
        for uid, total in totals.items()
    ]
    household_total = sum(totals.values(), Decimal("0"))
    return PerUserBreakdown(
        contributions=contribs,
        per_user=per_user,
        household_total=household_total,
        currency=currency,
    )


async def scan_tag_contributions(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> int:
    """Scan transactions tagged with goal tags and log tag_driven contributions.

    Idempotent: checks transaction_id before inserting.
    Returns count of new contributions logged.
    """
    goals_result = await session.execute(
        sa.select(Goal).where(
            Goal.household_id == household_id,
            Goal.status == str(GoalStatus.ACTIVE),
            Goal.archived_at.is_(None),
        )
    )
    goals = list(goals_result.scalars().all())

    logged = 0
    for goal in goals:
        tag_id_raw = goal.metadata_.get("tag_id")
        if not tag_id_raw:
            continue
        try:
            tag_id = uuid.UUID(str(tag_id_raw))
        except ValueError:
            continue

        allocations = await txn_svc.get_allocations_in_range(
            session,
            household_id=household_id,
            period_start=date(2000, 1, 1),
            period_end=date.today(),
            tag_ids=[tag_id],
        )

        for alloc in allocations:
            if alloc.transaction_id is None:
                continue
            try:
                await log_contribution(
                    session,
                    goal_id=goal.id,
                    household_id=household_id,
                    amount=alloc.amount,
                    currency=alloc.currency or goal.currency,
                    contributed_at=date.today(),
                    contribution_type=ContributionType.TAG_DRIVEN,
                    transaction_id=alloc.transaction_id,
                )
                logged += 1
            except ConflictError:
                pass

    return logged


# ---------------------------------------------------------------------------
# Burn-up computation
# ---------------------------------------------------------------------------


async def _get_goal_start_date(goal: Goal) -> date:
    """Infer goal start date from created_at (first possible contribution date)."""
    return goal.created_at.date()


async def compute_burn_up(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of_date: date | None = None,
) -> GoalSnapshot:
    """Compute and persist a burn-up snapshot for a goal.

    For debt_payoff type: reads DebtPlanSummary via debts.service as the
    effective target_amount if linked_debt_plan_id is set and no target
    override is configured.
    """
    from app.debts.service import get_summary as debts_get_summary

    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    as_of = as_of_date or date.today()

    target = goal.target_amount or Decimal("0")

    if (
        goal.goal_type == str(GoalType.DEBT_PAYOFF)
        and goal.linked_debt_plan_id is not None
        and goal.target_amount is None
    ):
        try:
            debt_summary = await debts_get_summary(
                session,
                plan_group_id=goal.linked_debt_plan_id,
                household_id=household_id,
            )
            target = debt_summary.total_paid
        except Exception:
            target = Decimal("0")

    start_date = await _get_goal_start_date(goal)

    contribs = await session.execute(
        sa.select(GoalContribution).where(
            GoalContribution.goal_id == goal_id,
            GoalContribution.contributed_at <= as_of,
        )
    )
    all_contribs = list(contribs.scalars().all())
    cumulative_actual = sum((c.amount for c in all_contribs), Decimal("0")).quantize(
        _CENT, ROUND_HALF_UP
    )

    cutoff_30d = as_of - timedelta(days=_DAYS_TRAILING)
    trailing_30d = sum(
        (c.amount for c in all_contribs if c.contributed_at >= cutoff_30d),
        Decimal("0"),
    ).quantize(_CENT, ROUND_HALF_UP)

    fields = compute_burn_up_pure(
        target_amount=target,
        start_date=start_date,
        target_date=goal.target_date,
        as_of_date=as_of,
        cumulative_actual=cumulative_actual,
        trailing_30d_actual=trailing_30d,
        thresholds=goal.metadata_.get("thresholds"),
    )

    from app.platform.time import utcnow as _utcnow

    snap = GoalSnapshot(
        goal_id=goal_id,
        snapshot_date=as_of,
        cumulative_actual=cumulative_actual,
        currency=goal.currency,
        computed_at=_utcnow(),
        **fields,
    )
    session.add(snap)
    await session.flush()

    logger.info(
        "goal.burn_up.computed",
        goal_id=str(goal_id),
        progress_pct=str(fields["progress_pct"]),
        status=fields["burn_up_status"],
    )
    return snap


async def get_latest_snapshot(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> GoalSnapshot:
    """Return most recent GoalSnapshot for a goal."""
    await get_goal(session, goal_id=goal_id, household_id=household_id)
    result = await session.execute(
        sa.select(GoalSnapshot)
        .where(GoalSnapshot.goal_id == goal_id)
        .order_by(GoalSnapshot.snapshot_date.desc(), GoalSnapshot.computed_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if snap is None:
        raise NotFoundError("no snapshot found -- run compute_burn_up first")
    return snap


async def list_snapshots(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[GoalSnapshot]:
    """Return all snapshots for a goal ordered by date."""
    await get_goal(session, goal_id=goal_id, household_id=household_id)
    result = await session.execute(
        sa.select(GoalSnapshot)
        .where(GoalSnapshot.goal_id == goal_id)
        .order_by(GoalSnapshot.snapshot_date, GoalSnapshot.computed_at)
    )
    return list(result.scalars().all())


async def get_all_status(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    as_of_date: date | None = None,
) -> list[GoalSnapshot]:
    """Compute burn-up for all active goals and return snapshots."""
    goals = await list_goals(session, household_id=household_id, status=GoalStatus.ACTIVE)
    snapshots = []
    for goal in goals:
        try:
            snap = await compute_burn_up(
                session, goal_id=goal.id, household_id=household_id, as_of_date=as_of_date
            )
            snapshots.append(snap)
        except Exception as exc:
            logger.warning(
                "goal.get_all_status.skip",
                goal_id=str(goal.id),
                error=str(exc),
            )
    return snapshots


# ---------------------------------------------------------------------------
# Completion policies
# ---------------------------------------------------------------------------


async def check_completion(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Apply completion policy if progress_pct >= 100.

    prompt_on_complete (DEFAULT): emits Recommendation for HITL.
    archive_on_complete: sets status=completed and archives.
    auto_extend: increments target_amount by auto_extend_amount.
    auto_clone: archives current, creates new active clone.
    convert_to_recurring: archives, emits Recommendation.
    """
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    if goal.status not in (str(GoalStatus.ACTIVE), str(GoalStatus.PAUSED)):
        return

    snap = await compute_burn_up(session, goal_id=goal_id, household_id=household_id)
    if snap.progress_pct < Decimal("100"):
        return

    policy = CompletionPolicy(goal.completion_policy)

    if policy == CompletionPolicy.ARCHIVE_ON_COMPLETE:
        now = utcnow()
        goal.status = str(GoalStatus.COMPLETED)
        goal.archived_at = now
        goal.archived_by = actor_id
        await session.flush()
        session.add(
            AuditEvent(
                actor_type=str(ActorType.SYSTEM),
                actor_id=actor_id,
                actor_source="goal_engine",
                household_id=household_id,
                entity_type="goal",
                entity_id=goal_id,
                operation=str(AuditOperation.ARCHIVE),
                delta=[{"op": "replace", "path": "/status", "value": "completed"}],
            )
        )

    elif policy == CompletionPolicy.PROMPT_ON_COMPLETE:
        await rec_svc.create(
            session,
            household_id=household_id,
            source=RecommendationSource.GOAL_ENGINE,
            target_subsystem="goals",
            target_entity_id=goal_id,
            proposed_value={
                "goal_id": str(goal_id),
                "progress_pct": str(snap.progress_pct),
                "action": "complete",
                "options": ["archive", "extend", "clone"],
            },
            rationale_text=(
                f"Goal '{goal.name}' has reached {snap.progress_pct:.1f}% of target. "
                f"Choose how to handle completion."
            ),
            rationale_data={"snapshot_id": str(snap.id)},
        )

    elif policy == CompletionPolicy.AUTO_EXTEND:
        extend_by = goal.auto_extend_amount or Decimal("0")
        if extend_by <= Decimal("0"):
            extend_by = goal.target_amount or Decimal("0")
        goal.target_amount = (goal.target_amount or Decimal("0")) + extend_by
        await session.flush()
        logger.info("goal.auto_extend", goal_id=str(goal_id), new_target=str(goal.target_amount))

    elif policy == CompletionPolicy.AUTO_CLONE:
        now = utcnow()
        goal.status = str(GoalStatus.COMPLETED)
        goal.archived_at = now
        goal.archived_by = actor_id
        await session.flush()

        new_goal = Goal(
            household_id=goal.household_id,
            name=goal.name,
            description=goal.description,
            goal_type=goal.goal_type,
            status=str(GoalStatus.ACTIVE),
            target_amount=goal.target_amount,
            currency=goal.currency,
            target_date=goal.target_date,
            funding_strategy=goal.funding_strategy,
            completion_policy=goal.completion_policy,
            auto_extend_amount=goal.auto_extend_amount,
            owner_id=goal.owner_id,
            linked_debt_plan_id=goal.linked_debt_plan_id,
            linked_category_id=goal.linked_category_id,
            minimum_balance_threshold=goal.minimum_balance_threshold,
            metadata_=dict(goal.metadata_),
        )
        session.add(new_goal)
        await session.flush()
        logger.info("goal.auto_clone", original=str(goal_id), clone=str(new_goal.id))

    elif policy == CompletionPolicy.CONVERT_TO_RECURRING:
        now = utcnow()
        goal.status = str(GoalStatus.COMPLETED)
        goal.archived_at = now
        goal.archived_by = actor_id
        await session.flush()

        await rec_svc.create(
            session,
            household_id=household_id,
            source=RecommendationSource.GOAL_ENGINE,
            target_subsystem="goals",
            target_entity_id=goal_id,
            proposed_value={
                "goal_id": str(goal_id),
                "original_name": goal.name,
                "suggested_type": str(GoalType.RECURRING_CONTRIBUTION),
                "suggested_amount": str(snap.actual_pace),
                "currency": goal.currency,
            },
            rationale_text=(
                f"Goal '{goal.name}' completed. Consider converting to a recurring "
                f"contribution goal of {snap.actual_pace:.2f} {goal.currency}/month."
            ),
            rationale_data={"snapshot_id": str(snap.id)},
        )

    session.add(
        AuditEvent(
            actor_type=str(ActorType.SYSTEM),
            actor_id=actor_id,
            actor_source="goal_engine",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.APPLY),
            delta=[
                {"op": "add", "path": "/completion_policy_applied", "value": str(policy)},
                {"op": "add", "path": "/progress_pct", "value": str(snap.progress_pct)},
            ],
        )
    )
    await session.flush()


async def manual_complete(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Manually trigger completion check regardless of progress_pct."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)

    snap = await compute_burn_up(session, goal_id=goal_id, household_id=household_id)

    await rec_svc.create(
        session,
        household_id=household_id,
        source=RecommendationSource.GOAL_ENGINE,
        target_subsystem="goals",
        target_entity_id=goal_id,
        proposed_value={
            "goal_id": str(goal_id),
            "progress_pct": str(snap.progress_pct),
            "action": "manual_complete",
            "options": ["archive", "extend", "clone"],
        },
        rationale_text=(
            f"Manual completion triggered for goal '{goal.name}' "
            f"at {snap.progress_pct:.1f}% of target."
        ),
        rationale_data={"snapshot_id": str(snap.id)},
    )

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="goal",
            entity_id=goal_id,
            operation=str(AuditOperation.APPLY),
            delta=[{"op": "add", "path": "/manual_complete", "value": True}],
        )
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Cross-module checks (emit Recommendations only)
# ---------------------------------------------------------------------------


async def check_minimum_balance(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
) -> None:
    """For minimum_balance goals: fetch account balance and alert if below threshold."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    if goal.goal_type != str(GoalType.MINIMUM_BALANCE):
        return
    if goal.minimum_balance_threshold is None:
        return

    source_result = await session.execute(
        sa.select(GoalFundingSource).where(
            GoalFundingSource.goal_id == goal_id,
            GoalFundingSource.source_type == str(FundingSourceType.ACCOUNT),
        )
    )
    sources = list(source_result.scalars().all())
    if not sources:
        return

    for src in sources:
        if src.source_id is None:
            continue
        try:
            account = await accounts_svc.get_account(
                session, account_id=src.source_id, household_id=household_id
            )
        except accounts_svc.NotFoundError:
            continue

        balance = account.current_balance
        if balance < goal.minimum_balance_threshold:
            await rec_svc.create(
                session,
                household_id=household_id,
                source=RecommendationSource.GOAL_ENGINE,
                target_subsystem="goals",
                target_entity_id=goal_id,
                proposed_value={
                    "goal_id": str(goal_id),
                    "account_id": str(src.source_id),
                    "current_balance": str(balance),
                    "threshold": str(goal.minimum_balance_threshold),
                    "shortfall": str(goal.minimum_balance_threshold - balance),
                },
                rationale_text=(
                    f"Account balance {balance:.2f} {goal.currency} is below "
                    f"minimum threshold {goal.minimum_balance_threshold:.2f} "
                    f"for goal '{goal.name}'."
                ),
                rationale_data={"account_id": str(src.source_id)},
            )
            logger.info(
                "goal.minimum_balance.alert",
                goal_id=str(goal_id),
                balance=str(balance),
                threshold=str(goal.minimum_balance_threshold),
            )


async def check_category_reduction(
    session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> None:
    """For category_reduction goals: compare spend vs target and alert if trending over."""
    goal = await get_goal(session, goal_id=goal_id, household_id=household_id)
    if goal.goal_type != str(GoalType.CATEGORY_REDUCTION):
        return
    if goal.linked_category_id is None or goal.target_amount is None:
        return

    allocations = await txn_svc.get_allocations_in_range(
        session,
        household_id=household_id,
        period_start=period_start,
        period_end=period_end,
        category_ids=[goal.linked_category_id],
        direction="debit",
    )

    actual_spend = sum((a.amount for a in allocations), Decimal("0")).quantize(_CENT, ROUND_HALF_UP)

    if actual_spend > goal.target_amount:
        over_by = (actual_spend - goal.target_amount).quantize(_CENT, ROUND_HALF_UP)
        await rec_svc.create(
            session,
            household_id=household_id,
            source=RecommendationSource.GOAL_ENGINE,
            target_subsystem="goals",
            target_entity_id=goal_id,
            proposed_value={
                "goal_id": str(goal_id),
                "category_id": str(goal.linked_category_id),
                "period_start": str(period_start),
                "period_end": str(period_end),
                "actual_spend": str(actual_spend),
                "target_spend": str(goal.target_amount),
                "over_by": str(over_by),
            },
            rationale_text=(
                f"Category spend {actual_spend:.2f} {goal.currency} exceeds "
                f"reduction target {goal.target_amount:.2f} by {over_by:.2f} "
                f"for goal '{goal.name}'."
            ),
            rationale_data={
                "category_id": str(goal.linked_category_id),
                "period": f"{period_start}/{period_end}",
            },
        )
        logger.info(
            "goal.category_reduction.alert",
            goal_id=str(goal_id),
            actual=str(actual_spend),
            target=str(goal.target_amount),
        )
