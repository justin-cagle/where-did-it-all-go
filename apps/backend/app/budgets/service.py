"""Budgets service layer.

All cross-module data access goes through service interfaces — no direct DB joins
across module boundaries.

Public interface:
  create_budget(...)                          -> Budget
  get_budget(budget_group_id, household_id)   -> Budget (current version)
  get_active_budget(budget_group_id, as_of)  -> Budget (version for as_of date)
  update_budget(...)                          -> Budget (new version)
  archive_budget(...)                         -> Budget
  list_budgets(household_id)                  -> list[Budget]
  list_budget_history(budget_group_id, ...)   -> list[Budget]
  create_budget_line(...)                     -> BudgetLine
  get_budget_line(...)                        -> BudgetLine
  update_budget_line(...)                     -> BudgetLine
  archive_budget_line(...)                    -> BudgetLine
  list_budget_lines(budget_id, ...)           -> list[BudgetLine]
  resolve_period(budget, reference_date)      -> (period_start, period_end)
  compute_actuals(...)                        -> list[BudgetLineResult]
  compute_expected_income(...)               -> Decimal | None
  get_status(...)                             -> BudgetStatusSnapshot
  set_period_income(...)                      -> BudgetPeriodIncome
  list_periods(...)                           -> list[BudgetPeriodActual]
  period_close(session, household_id)         -> dict[str, int]
"""

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.budgets.enums import (
    BudgetLineStatus,
    BudgetMethod,
    BudgetPeriod,
    ExpectedIncomeStrategy,
    RolloverPolicy,
)
from app.budgets.models import Budget, BudgetLine, BudgetPeriodActual, BudgetPeriodIncome
from app.platform.ids import new_uuid
from app.platform.time import utcnow

logger = structlog.get_logger(__name__)

_FIFTY_THIRTY_TWENTY_TOLERANCE = Decimal("0.02")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a state constraint."""


class ValidationError(Exception):
    """Budget method constraint violated."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BudgetLineResult:
    line: BudgetLine
    period_actual: BudgetPeriodActual | None
    planned: Decimal
    actual: Decimal
    carried_in: Decimal
    remaining: Decimal
    status: BudgetLineStatus


@dataclass
class BudgetStatusSnapshot:
    budget: Budget
    period_start: date
    period_end: date
    expected_income: Decimal | None
    lines: list[BudgetLineResult] = field(default_factory=list[BudgetLineResult])


# ---------------------------------------------------------------------------
# Period resolution (pure — no DB access)
# ---------------------------------------------------------------------------


def resolve_period(budget: Budget, reference_date: date) -> tuple[date, date]:
    """Return (period_start, period_end) for the period containing reference_date.

    For pay-period budgets (pay_period_income_source_id set), falls back to
    biweekly anchored from budget.start_date.
    """
    period = BudgetPeriod(budget.period)

    if period == BudgetPeriod.MONTHLY:
        first = reference_date.replace(day=1)
        last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
        return first, reference_date.replace(day=last_day)

    if period == BudgetPeriod.WEEKLY:
        # Monday-based week
        monday = reference_date - timedelta(days=reference_date.weekday())
        return monday, monday + timedelta(days=6)

    if period == BudgetPeriod.BIWEEKLY or period == BudgetPeriod.CUSTOM:
        # Anchor on budget start_date; find which 14-day cycle contains reference_date
        anchor = budget.start_date
        delta = (reference_date - anchor).days
        cycle_num = delta // 14
        period_start = anchor + timedelta(days=cycle_num * 14)
        return period_start, period_start + timedelta(days=13)

    if period == BudgetPeriod.SEMIMONTHLY:
        if reference_date.day <= 15:
            first = reference_date.replace(day=1)
            return first, reference_date.replace(day=15)
        else:
            first = reference_date.replace(day=16)
            last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
            return first, reference_date.replace(day=last_day)

    if period == BudgetPeriod.ANNUAL:
        return date(reference_date.year, 1, 1), date(reference_date.year, 12, 31)

    # Fallback — should not reach here with valid enum
    raise ValidationError(f"unsupported budget period: {budget.period!r}")


# ---------------------------------------------------------------------------
# Rollover calculation (pure — no DB access)
# ---------------------------------------------------------------------------


def _compute_rollover(
    *,
    planned: Decimal,
    actual: Decimal,
    carried_in: Decimal,
    rollover_policy: RolloverPolicy,
    rollover_cap: Decimal | None,
) -> Decimal:
    """Return carried_out for the closing period under the given rollover policy.

    Positive carried_out = credit (unspent) carried forward.
    Negative carried_out = debt carried forward (debt_carry policy only).
    """
    effective_planned = planned + carried_in

    if rollover_policy == RolloverPolicy.NONE:
        return Decimal("0")

    if rollover_policy == RolloverPolicy.ACCUMULATE:
        return max(Decimal("0"), effective_planned - actual)

    if rollover_policy == RolloverPolicy.ACCUMULATE_CAPPED:
        unspent = max(Decimal("0"), effective_planned - actual)
        cap = rollover_cap if rollover_cap is not None else Decimal("0")
        return min(cap, unspent)

    if rollover_policy == RolloverPolicy.DEBT_CARRY:
        # Positive = unspent, negative = overspend
        return effective_planned - actual

    if rollover_policy == RolloverPolicy.RESET_ON_OVERSPEND:
        if actual > effective_planned:
            return Decimal("0")
        return effective_planned - actual

    return Decimal("0")


def _line_status(*, actual: Decimal, effective_planned: Decimal) -> BudgetLineStatus:
    if actual > effective_planned:
        return BudgetLineStatus.OVER
    if actual >= effective_planned * Decimal("0.9"):
        return BudgetLineStatus.ON_TRACK
    return BudgetLineStatus.UNDER


# ---------------------------------------------------------------------------
# Budget CRUD (versioned)
# ---------------------------------------------------------------------------


async def create_budget(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    period: BudgetPeriod,
    start_date: date,
    method: BudgetMethod,
    end_date: date | None = None,
    owner_id: uuid.UUID | None = None,
    expected_income_strategy: ExpectedIncomeStrategy = ExpectedIncomeStrategy.FIXED,
    expected_income: Decimal | None = None,
    currency: str = "USD",
    income_rolling_periods: int = 3,
    scope_accounts: list[uuid.UUID] | None = None,
    scope_categories: list[uuid.UUID] | None = None,
    scope_tags: list[uuid.UUID] | None = None,
    pay_period_income_source_id: uuid.UUID | None = None,
) -> Budget:
    """Create the first version of a new budget."""
    budget_id = new_uuid()
    budget = Budget(
        id=budget_id,
        budget_group_id=budget_id,  # First version: group == self
        household_id=household_id,
        owner_id=owner_id,
        name=name,
        period=str(period),
        start_date=start_date,
        end_date=end_date,
        method=str(method),
        expected_income_strategy=str(expected_income_strategy),
        expected_income=expected_income,
        currency=currency.upper(),
        income_rolling_periods=income_rolling_periods,
        scope_accounts=[str(a) for a in (scope_accounts or [])],
        scope_categories=[str(c) for c in (scope_categories or [])],
        scope_tags=[str(t) for t in (scope_tags or [])],
        pay_period_income_source_id=pay_period_income_source_id,
        effective_from=start_date,
        effective_to=None,
    )
    session.add(budget)
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="budget",
        entity_id=budget_id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
        actor_id=actor_id,
    )
    logger.info("budget.created", budget_id=str(budget_id), household_id=str(household_id))
    return budget


async def get_budget(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> Budget:
    """Return the current (effective_to IS NULL) version of a budget."""
    result = await session.execute(
        sa.select(Budget).where(
            Budget.budget_group_id == budget_group_id,
            Budget.household_id == household_id,
            Budget.effective_to.is_(None),
            Budget.archived_at.is_(None),
        )
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        raise NotFoundError("budget not found")
    return budget


async def get_active_budget(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of_date: date,
) -> Budget:
    """Return the budget version active on as_of_date."""
    result = await session.execute(
        sa.select(Budget)
        .where(
            Budget.budget_group_id == budget_group_id,
            Budget.household_id == household_id,
            Budget.effective_from <= as_of_date,
            sa.or_(Budget.effective_to.is_(None), Budget.effective_to >= as_of_date),
            Budget.archived_at.is_(None),
        )
        .order_by(Budget.effective_from.desc())
        .limit(1)
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        raise NotFoundError("no budget version active on that date")
    return budget


async def update_budget(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    effective_from: date | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Budget:
    """Edit a budget by closing the current version and creating a new one.

    Caller provides only the fields to change; unchanged fields are copied
    from the current version. Edits never rewrite historical rows.
    """
    current = await get_budget(session, budget_group_id=budget_group_id, household_id=household_id)
    new_effective_from = effective_from or date.today()

    # Close current version
    current.effective_to = new_effective_from - timedelta(days=1)
    await session.flush()

    # Build new version by copying current, applying changes
    fields: dict[str, Any] = {
        "name": current.name,
        "period": current.period,
        "start_date": current.start_date,
        "end_date": current.end_date,
        "owner_id": current.owner_id,
        "method": current.method,
        "expected_income_strategy": current.expected_income_strategy,
        "expected_income": current.expected_income,
        "currency": current.currency,
        "income_rolling_periods": current.income_rolling_periods,
        "scope_accounts": list(current.scope_accounts),
        "scope_categories": list(current.scope_categories),
        "scope_tags": list(current.scope_tags),
        "pay_period_income_source_id": current.pay_period_income_source_id,
    }
    for k, v in kwargs.items():
        if v is not None and k in fields:
            if k in ("scope_accounts", "scope_categories", "scope_tags") and isinstance(v, list):
                fields[k] = [str(x) for x in v]  # type: ignore[union-attr]
            elif k == "currency" and isinstance(v, str):
                fields[k] = v.upper()
            else:
                is_enum = isinstance(v, BudgetPeriod | BudgetMethod | ExpectedIncomeStrategy)
                fields[k] = str(v) if is_enum else v

    new_version = Budget(
        budget_group_id=budget_group_id,
        household_id=household_id,
        effective_from=new_effective_from,
        effective_to=None,
        **fields,
    )
    session.add(new_version)
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="budget",
        entity_id=new_version.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/budget_group_id", "value": str(budget_group_id)}],
        actor_id=actor_id,
    )
    logger.info(
        "budget.updated",
        budget_group_id=str(budget_group_id),
        new_version_id=str(new_version.id),
    )
    return new_version


async def archive_budget(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Budget:
    """Soft-delete all versions of a budget."""
    result = await session.execute(
        sa.select(Budget).where(
            Budget.budget_group_id == budget_group_id,
            Budget.household_id == household_id,
            Budget.archived_at.is_(None),
        ),
        execution_options={"include_archived": False},
    )
    budgets = list(result.scalars().all())
    if not budgets:
        raise NotFoundError("budget not found")

    now = utcnow()
    for b in budgets:
        b.archived_at = now
        b.archived_by = actor_id
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="budget",
        entity_id=budget_group_id,
        operation=AuditOperation.ARCHIVE,
        delta=[],
        actor_id=actor_id,
    )
    logger.info("budget.archived", budget_group_id=str(budget_group_id))
    # Return whichever was current
    current = next((b for b in budgets if b.effective_to is None), budgets[0])
    return current


async def list_budgets(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[Budget]:
    """Return all current budget versions for a household."""
    result = await session.execute(
        sa.select(Budget)
        .where(
            Budget.household_id == household_id,
            Budget.effective_to.is_(None),
        )
        .order_by(Budget.created_at.desc())
    )
    return list(result.scalars().all())


async def list_budget_history(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[Budget]:
    """Return all versions of a budget, newest effective_from first."""
    result = await session.execute(
        sa.select(Budget)
        .where(
            Budget.budget_group_id == budget_group_id,
            Budget.household_id == household_id,
        )
        .order_by(Budget.effective_from.desc()),
        execution_options={"include_archived": True},
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# BudgetLine CRUD
# ---------------------------------------------------------------------------


async def create_budget_line(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    category_id: uuid.UUID,
    planned_amount: Decimal,
    currency: str = "USD",
    tag_id: uuid.UUID | None = None,
    rollover_policy: RolloverPolicy = RolloverPolicy.NONE,
    rollover_cap: Decimal | None = None,
) -> BudgetLine:
    # Verify budget exists and belongs to household
    await get_budget(session, budget_group_id=budget_group_id, household_id=household_id)

    line = BudgetLine(
        budget_id=budget_group_id,
        household_id=household_id,
        category_id=category_id,
        tag_id=tag_id,
        planned_amount=planned_amount,
        currency=currency.upper(),
        rollover_policy=str(rollover_policy),
        rollover_cap=rollover_cap,
        carried_amount=Decimal("0"),
    )
    session.add(line)
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="budget_line",
        entity_id=line.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/planned_amount", "value": str(planned_amount)}],
        actor_id=actor_id,
    )
    return line


async def get_budget_line(
    session: AsyncSession,
    *,
    line_id: uuid.UUID,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> BudgetLine:
    result = await session.execute(
        sa.select(BudgetLine).where(
            BudgetLine.id == line_id,
            BudgetLine.budget_id == budget_group_id,
            BudgetLine.household_id == household_id,
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundError("budget line not found")
    return line


async def update_budget_line(
    session: AsyncSession,
    *,
    line_id: uuid.UUID,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    planned_amount: Decimal | None = None,
    currency: str | None = None,
    rollover_policy: RolloverPolicy | None = None,
    rollover_cap: Decimal | None = None,
) -> BudgetLine:
    line = await get_budget_line(
        session, line_id=line_id, budget_group_id=budget_group_id, household_id=household_id
    )
    delta: list[dict[str, Any]] = []

    if planned_amount is not None:
        delta.append({"op": "replace", "path": "/planned_amount", "value": str(planned_amount)})
        line.planned_amount = planned_amount
    if currency is not None:
        line.currency = currency.upper()
    if rollover_policy is not None:
        delta.append({"op": "replace", "path": "/rollover_policy", "value": str(rollover_policy)})
        line.rollover_policy = str(rollover_policy)
    if rollover_cap is not None:
        line.rollover_cap = rollover_cap

    await session.flush()
    if delta:
        await audit_service.log(
            session,
            household_id=household_id,
            actor_type=ActorType.USER,
            actor_source="user_action",
            entity_type="budget_line",
            entity_id=line_id,
            operation=AuditOperation.UPDATE,
            delta=delta,
            actor_id=actor_id,
        )
    return line


async def archive_budget_line(
    session: AsyncSession,
    *,
    line_id: uuid.UUID,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> BudgetLine:
    line = await get_budget_line(
        session, line_id=line_id, budget_group_id=budget_group_id, household_id=household_id
    )
    line.archived_at = utcnow()
    line.archived_by = actor_id
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="budget_line",
        entity_id=line_id,
        operation=AuditOperation.ARCHIVE,
        delta=[],
        actor_id=actor_id,
    )
    return line


async def list_budget_lines(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[BudgetLine]:
    result = await session.execute(
        sa.select(BudgetLine)
        .where(
            BudgetLine.budget_id == budget_group_id,
            BudgetLine.household_id == household_id,
        )
        .order_by(BudgetLine.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Actuals computation
# ---------------------------------------------------------------------------


async def compute_actuals(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    period_start: date,
    period_end: date,
    as_of_date: date | None = None,
) -> list[BudgetLineResult]:
    """Compute and persist actuals for all lines in a budget for one period.

    Fetches SplitAllocations via transactions.service (no direct join).
    Applies rollover logic and writes/updates BudgetPeriodActual rows.
    Returns per-line status snapshot.
    """
    from app.transactions import service as tx_service

    ref_date = as_of_date or period_end
    budget = await get_active_budget(
        session, budget_group_id=budget_group_id, household_id=household_id, as_of_date=ref_date
    )
    lines = await list_budget_lines(
        session, budget_group_id=budget_group_id, household_id=household_id
    )

    # Scope parameters for allocation fetch (empty list = any)
    scope_accounts = [uuid.UUID(a) for a in budget.scope_accounts] or None
    scope_categories = [uuid.UUID(c) for c in budget.scope_categories] or None
    scope_tags = [uuid.UUID(t) for t in budget.scope_tags] or None

    allocations = await tx_service.get_allocations_in_range(
        session,
        household_id=household_id,
        period_start=period_start,
        period_end=period_end,
        account_ids=scope_accounts,
        category_ids=scope_categories,
        tag_ids=scope_tags,
        direction="debit",
    )

    # Build category -> allocations lookup
    from collections import defaultdict

    alloc_by_category: dict[uuid.UUID | None, list[Any]] = defaultdict(list)
    for alloc in allocations:
        alloc_by_category[alloc.category_id].append(alloc)

    results: list[BudgetLineResult] = []

    for line in lines:
        # Sum actuals for this line
        line_allocations = alloc_by_category.get(line.category_id, [])
        if line.tag_id is not None:
            tag_str = str(line.tag_id)
            line_allocations = [
                a for a in line_allocations if tag_str in [str(t) for t in a.tag_ids]
            ]

        actual = sum((a.amount for a in line_allocations), Decimal("0"))
        carried_in = line.carried_amount
        effective_planned = line.planned_amount + carried_in

        # Compute rollover
        policy = RolloverPolicy(line.rollover_policy)
        carried_out = _compute_rollover(
            planned=line.planned_amount,
            actual=actual,
            carried_in=carried_in,
            rollover_policy=policy,
            rollover_cap=line.rollover_cap,
        )

        remaining = effective_planned - actual
        status = _line_status(actual=actual, effective_planned=effective_planned)

        # Upsert BudgetPeriodActual
        existing_result = await session.execute(
            sa.select(BudgetPeriodActual).where(
                BudgetPeriodActual.budget_line_id == line.id,
                BudgetPeriodActual.period_start == period_start,
            )
        )
        period_actual = existing_result.scalar_one_or_none()
        if period_actual is None:
            period_actual = BudgetPeriodActual(
                budget_id=budget_group_id,
                budget_line_id=line.id,
                period_start=period_start,
                period_end=period_end,
                planned_amount=line.planned_amount,
                currency=line.currency,
                actual_amount=actual,
                carried_in=carried_in,
                carried_out=carried_out,
            )
            session.add(period_actual)
        else:
            period_actual.period_end = period_end
            period_actual.planned_amount = line.planned_amount
            period_actual.actual_amount = actual
            period_actual.carried_in = carried_in
            period_actual.carried_out = carried_out

        await session.flush()

        results.append(
            BudgetLineResult(
                line=line,
                period_actual=period_actual,
                planned=line.planned_amount,
                actual=actual,
                carried_in=carried_in,
                remaining=remaining,
                status=status,
            )
        )

    # Method enforcement
    await _enforce_method(session, budget=budget, results=results, household_id=household_id)

    return results


async def _enforce_method(
    session: AsyncSession,
    *,
    budget: Budget,
    results: list[BudgetLineResult],
    household_id: uuid.UUID,
) -> None:
    """Apply method-specific enforcement after actuals are computed."""
    method = BudgetMethod(budget.method)

    if method == BudgetMethod.ENVELOPE:
        # Flag depleted lines via HITL recommendations
        from app.recommendations import service as rec_service
        from app.recommendations.enums import RecommendationSource

        for r in results:
            if r.status == BudgetLineStatus.OVER:
                await rec_service.create(
                    session,
                    household_id=household_id,
                    source=RecommendationSource.INGEST,
                    target_subsystem="budgets",
                    target_entity_id=r.line.id,
                    proposed_value={"action": "envelope_depleted", "line_id": str(r.line.id)},
                    rationale_text=(
                        f"Budget line for category {r.line.category_id} is depleted: "
                        f"spent {r.actual} of {r.planned} planned."
                    ),
                    rationale_data={
                        "budget_group_id": str(budget.budget_group_id),
                        "line_id": str(r.line.id),
                        "actual": str(r.actual),
                        "planned": str(r.planned),
                    },
                )

    elif method == BudgetMethod.FIFTY_THIRTY_TWENTY:
        from app.classification import service as clf_service

        category_ids = [r.line.category_id for r in results]
        roles = await clf_service.get_categories_budget_roles(
            session, household_id=household_id, category_ids=category_ids
        )
        total_planned = sum(r.planned for r in results) or Decimal("1")
        buckets: dict[str, Decimal] = {
            "needs": Decimal("0"),
            "wants": Decimal("0"),
            "savings": Decimal("0"),
        }
        for r in results:
            role = roles.get(r.line.category_id, "uncategorized")
            if role in buckets:
                buckets[role] += r.planned
        targets = {"needs": Decimal("0.50"), "wants": Decimal("0.30"), "savings": Decimal("0.20")}
        for bucket, target in targets.items():
            ratio = buckets[bucket] / total_planned
            if abs(ratio - target) > _FIFTY_THIRTY_TWENTY_TOLERANCE:
                logger.warning(
                    "budget.fifty_thirty_twenty.ratio_off",
                    bucket=bucket,
                    expected=str(target),
                    actual=str(ratio),
                    budget_group_id=str(budget.budget_group_id),
                )


# ---------------------------------------------------------------------------
# Expected income computation
# ---------------------------------------------------------------------------


async def compute_expected_income(
    session: AsyncSession,
    *,
    budget: Budget,
    period_start: date,
    period_end: date,
    household_id: uuid.UUID,
) -> Decimal | None:
    """Return expected income for a period given the budget's income strategy."""
    strategy = ExpectedIncomeStrategy(budget.expected_income_strategy)

    if strategy == ExpectedIncomeStrategy.FIXED:
        return budget.expected_income

    if strategy == ExpectedIncomeStrategy.FROM_INCOME_SOURCES:
        from app.classification import service as clf_service

        return await clf_service.get_income_sources_projected_amount(
            session,
            household_id=household_id,
            period_start=period_start,
            period_end=period_end,
        )

    if strategy == ExpectedIncomeStrategy.LAST_PERIOD_ACTUAL:
        from app.transactions import service as tx_service

        period_length = (period_end - period_start).days + 1
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_length - 1)

        scope_accounts = [uuid.UUID(a) for a in budget.scope_accounts] or None
        scope_categories = [uuid.UUID(c) for c in budget.scope_categories] or None
        scope_tags = [uuid.UUID(t) for t in budget.scope_tags] or None

        credit_allocs = await tx_service.get_allocations_in_range(
            session,
            household_id=household_id,
            period_start=prev_start,
            period_end=prev_end,
            account_ids=scope_accounts,
            category_ids=scope_categories,
            tag_ids=scope_tags,
            direction="credit",
        )
        return sum((a.amount for a in credit_allocs), Decimal("0")) or None

    if strategy == ExpectedIncomeStrategy.ROLLING_AVERAGE:
        from app.transactions import service as tx_service

        n = budget.income_rolling_periods
        period_length = (period_end - period_start).days + 1
        scope_accounts = [uuid.UUID(a) for a in budget.scope_accounts] or None
        scope_categories = [uuid.UUID(c) for c in budget.scope_categories] or None
        scope_tags = [uuid.UUID(t) for t in budget.scope_tags] or None

        totals: list[Decimal] = []
        for i in range(1, n + 1):
            p_end = period_start - timedelta(days=(i - 1) * period_length + 1)
            p_start = p_end - timedelta(days=period_length - 1)
            allocs = await tx_service.get_allocations_in_range(
                session,
                household_id=household_id,
                period_start=p_start,
                period_end=p_end,
                account_ids=scope_accounts,
                category_ids=scope_categories,
                tag_ids=scope_tags,
                direction="credit",
            )
            totals.append(sum((a.amount for a in allocs), Decimal("0")))

        if not totals:
            return None
        return sum(totals, Decimal("0")) / Decimal(len(totals))

    if strategy == ExpectedIncomeStrategy.MANUAL_PER_PERIOD:
        result = await session.execute(
            sa.select(BudgetPeriodIncome).where(
                BudgetPeriodIncome.budget_group_id == budget.budget_group_id,
                BudgetPeriodIncome.period_start == period_start,
            )
        )
        override = result.scalar_one_or_none()
        return override.expected_income if override is not None else None

    return None


# ---------------------------------------------------------------------------
# Budget status snapshot
# ---------------------------------------------------------------------------


async def get_status(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of_date: date,
) -> BudgetStatusSnapshot:
    """Return a full status snapshot for a budget on as_of_date."""
    budget = await get_active_budget(
        session, budget_group_id=budget_group_id, household_id=household_id, as_of_date=as_of_date
    )
    period_start, period_end = resolve_period(budget, as_of_date)

    expected_income = await compute_expected_income(
        session,
        budget=budget,
        period_start=period_start,
        period_end=period_end,
        household_id=household_id,
    )

    line_results = await compute_actuals(
        session,
        budget_group_id=budget_group_id,
        household_id=household_id,
        period_start=period_start,
        period_end=period_end,
        as_of_date=as_of_date,
    )

    return BudgetStatusSnapshot(
        budget=budget,
        period_start=period_start,
        period_end=period_end,
        expected_income=expected_income,
        lines=line_results,
    )


# ---------------------------------------------------------------------------
# Per-period income override
# ---------------------------------------------------------------------------


async def set_period_income(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
    period_start: date,
    expected_income: Decimal,
    currency: str = "USD",
) -> BudgetPeriodIncome:
    """Upsert a manual income override for a specific period."""
    result = await session.execute(
        sa.select(BudgetPeriodIncome).where(
            BudgetPeriodIncome.budget_group_id == budget_group_id,
            BudgetPeriodIncome.period_start == period_start,
        )
    )
    override = result.scalar_one_or_none()
    if override is None:
        override = BudgetPeriodIncome(
            budget_group_id=budget_group_id,
            household_id=household_id,
            period_start=period_start,
            expected_income=expected_income,
            currency=currency.upper(),
        )
        session.add(override)
    else:
        override.expected_income = expected_income
        override.currency = currency.upper()
    await session.flush()
    return override


# ---------------------------------------------------------------------------
# Period listing
# ---------------------------------------------------------------------------


async def list_periods(
    session: AsyncSession,
    *,
    budget_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[BudgetPeriodActual]:
    """Return all BudgetPeriodActual rows for a budget, newest first."""
    result = await session.execute(
        sa.select(BudgetPeriodActual)
        .join(BudgetLine, BudgetLine.id == BudgetPeriodActual.budget_line_id)
        .where(
            BudgetPeriodActual.budget_id == budget_group_id,
            BudgetLine.household_id == household_id,
        )
        .order_by(BudgetPeriodActual.period_start.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Period close (worker entry point)
# ---------------------------------------------------------------------------


async def period_close(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> dict[str, int]:
    """Close any periods that ended yesterday and open the next one.

    Idempotent: safe to call daily even when no period boundary has been crossed.
    Applies rollovers (updates BudgetLine.carried_amount) and writes audit events.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    budgets = await list_budgets(session, household_id=household_id)
    closed = 0
    skipped = 0

    for budget in budgets:
        period_start, period_end = resolve_period(budget, yesterday)

        if period_end != yesterday:
            skipped += 1
            continue

        lines = await list_budget_lines(
            session, budget_group_id=budget.budget_group_id, household_id=household_id
        )
        results = await compute_actuals(
            session,
            budget_group_id=budget.budget_group_id,
            household_id=household_id,
            period_start=period_start,
            period_end=period_end,
        )

        # Apply rollovers: update carried_amount on each line
        for r in results:
            policy = RolloverPolicy(r.line.rollover_policy)
            if policy != RolloverPolicy.NONE:
                carried = r.period_actual.carried_out if r.period_actual else Decimal("0")
                r.line.carried_amount = carried

        await session.flush()

        await audit_service.log(
            session,
            household_id=household_id,
            actor_type=ActorType.SYSTEM,
            actor_source="budget_period_close",
            entity_type="budget",
            entity_id=budget.budget_group_id,
            operation=AuditOperation.APPLY,
            delta=[
                {"op": "replace", "path": "/period_closed", "value": str(period_end)},
                {"op": "replace", "path": "/lines_closed", "value": len(lines)},
            ],
        )
        closed += 1

    await session.flush()
    logger.info(
        "budget.period_close.complete",
        household_id=str(household_id),
        closed=closed,
        skipped=skipped,
    )
    return {"closed": closed, "skipped": skipped}
