"""Debts service layer.

Owns payoff strategy computation, schedule simulation, versioned plan CRUD,
and Recommendation emission. Never writes directly to budgets tables.

All DebtAccount / DebtBalance data accessed via app.accounts public interface.

Public interface:
  create_plan(...)                                  -> DebtPlan
  get_plan(plan_group_id, household_id)             -> DebtPlan (current version)
  get_active_plan(plan_group_id, household_id, as_of_date) -> DebtPlan
  update_plan(...)                                  -> DebtPlan (new version)
  archive_plan(...)                                 -> DebtPlan
  list_plans(household_id)                          -> list[DebtPlan]
  list_plan_history(plan_group_id, household_id)    -> list[DebtPlan]
  compute_schedule(session, plan_group_id, household_id) -> DebtPlanSummary
  get_schedule(session, plan_group_id, household_id)     -> list[DebtPlanScheduleByAccount]
  get_summary(session, plan_group_id, household_id)      -> DebtPlanSummary
  compute_minimums_baseline(session, plan_group_id, household_id) -> BaselineSummary
  check_payment_deviation(...)                      -> Recommendation | None
  recommend_budget_line(...)                        -> Recommendation | None
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

import app.accounts as accounts_svc
import app.recommendations.service as rec_svc
from app.accounts.models import Account, DebtBalance
from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.debts.enums import DebtPlanMethod
from app.debts.models import DebtPlan, DebtPlanSchedule, DebtPlanSummary
from app.platform.ids import new_uuid
from app.platform.time import utcnow
from app.recommendations.enums import RecommendationSource

logger = structlog.get_logger(__name__)

_HORIZON_MONTHS = 60
_MIN_PAYMENT_PCT = Decimal("0.02")
_MIN_PAYMENT_FLOOR = Decimal("25.00")
_CENT = Decimal("0.01")


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
class AccountTranche:
    """One DebtBalance tranche ready for simulation."""

    balance_id: uuid.UUID
    account_id: uuid.UUID
    principal: Decimal
    apr: Decimal
    currency: str
    minimum_payment: Decimal


@dataclass
class AccountState:
    """Aggregated per-account simulation state across all tranches."""

    account_id: uuid.UUID
    tranches: list[AccountTranche]
    currency: str

    @property
    def total_balance(self) -> Decimal:
        return sum((t.principal for t in self.tranches), Decimal("0"))

    @property
    def total_minimum(self) -> Decimal:
        return sum((t.minimum_payment for t in self.tranches), Decimal("0"))

    @property
    def weighted_apr(self) -> Decimal:
        total = self.total_balance
        if total == Decimal("0"):
            return Decimal("0")
        return sum(t.apr * t.principal for t in self.tranches) / total


@dataclass
class BaselineSummary:
    total_interest: Decimal
    total_paid: Decimal
    months_to_payoff: int
    payoff_date: date | None
    currency: str


# ---------------------------------------------------------------------------
# Minimum payment calculation (pure)
# ---------------------------------------------------------------------------


def _compute_minimum(tranche: "AccountTranche") -> Decimal:
    """Return estimated monthly minimum for a balance tranche.

    Uses 2% of balance floor $25 as a conservative universal heuristic.
    For zero-balance tranches returns zero.
    """
    if tranche.principal <= Decimal("0"):
        return Decimal("0")
    pct_min = (tranche.principal * _MIN_PAYMENT_PCT).quantize(_CENT, ROUND_HALF_UP)
    return max(pct_min, _MIN_PAYMENT_FLOOR)


# ---------------------------------------------------------------------------
# Simulation engine (pure — no DB access)
# ---------------------------------------------------------------------------


def _sort_accounts(
    accounts: list[AccountState],
    method: DebtPlanMethod,
    account_ids_order: list[uuid.UUID],
) -> list[AccountState]:
    """Return accounts in priority order for extra-payment allocation."""
    if method == DebtPlanMethod.AVALANCHE:
        return sorted(accounts, key=lambda a: a.weighted_apr, reverse=True)
    if method == DebtPlanMethod.SNOWBALL:
        return sorted(accounts, key=lambda a: a.total_balance)
    if method == DebtPlanMethod.CUSTOM:
        order_map = {aid: i for i, aid in enumerate(account_ids_order)}
        return sorted(accounts, key=lambda a: order_map.get(a.account_id, 9999))
    return list(accounts)


@dataclass
class _PeriodRow:
    account_id: uuid.UUID
    period_date: date
    opening_balance: Decimal
    currency: str
    payment: Decimal
    principal: Decimal
    interest: Decimal
    closing_balance: Decimal
    is_payoff: bool


def simulate_schedule(
    accounts: list[AccountState],
    method: DebtPlanMethod,
    monthly_extra_payment: Decimal,
    snowball_flow: bool,
    account_ids_order: list[uuid.UUID],
    start_date: date,
) -> list[_PeriodRow]:
    """Simulate month-by-month debt payoff.

    Returns flat list of period rows across all accounts and months.
    Horizon capped at _HORIZON_MONTHS (60).

    Multi-tranche accounts: each tranche is an independent amortization stream;
    minimums are summed for the account total minimum payment.
    Extra payment always goes to the highest-priority account's first tranche.
    """
    if method == DebtPlanMethod.NONE or not accounts:
        return []

    ordered = _sort_accounts(accounts, method, account_ids_order)

    # Deep copy balances so simulation is pure
    balances: dict[uuid.UUID, Decimal] = {
        t.balance_id: t.principal for a in ordered for t in a.tranches
    }
    aprs: dict[uuid.UUID, Decimal] = {t.balance_id: t.apr for a in ordered for t in a.tranches}
    currencies: dict[uuid.UUID, str] = {a.account_id: a.currency for a in ordered}

    rows: list[_PeriodRow] = []

    redirected_extra = Decimal("0")

    for month_offset in range(_HORIZON_MONTHS):
        # First day of this payment month
        period_date = _add_months(start_date, month_offset)

        # Check if all paid off
        def _bal(bid: uuid.UUID) -> Decimal:
            return balances.get(bid, Decimal("0"))

        active_accounts = [
            a for a in ordered if any(_bal(t.balance_id) > Decimal("0") for t in a.tranches)
        ]
        if not active_accounts:
            break

        # Determine priority account (first active in ordered list)
        priority_account = active_accounts[0]

        # Build per-account payment for this period
        account_summaries: dict[uuid.UUID, tuple[Decimal, Decimal, Decimal, Decimal, bool]] = {}

        available_extra = monthly_extra_payment + redirected_extra
        redirected_extra = Decimal("0")

        for acct in ordered:
            total_opening = Decimal("0")
            total_payment = Decimal("0")
            total_principal = Decimal("0")
            total_interest = Decimal("0")
            total_closing = Decimal("0")
            acct_active = any(
                balances.get(t.balance_id, Decimal("0")) > Decimal("0") for t in acct.tranches
            )

            if not acct_active:
                account_summaries[acct.account_id] = (
                    Decimal("0"),
                    Decimal("0"),
                    Decimal("0"),
                    Decimal("0"),
                    False,
                )
                continue

            for tranche in acct.tranches:
                bal = balances.get(tranche.balance_id, Decimal("0"))
                if bal <= Decimal("0"):
                    continue

                monthly_rate = tranche.apr / Decimal(12)
                interest = (bal * monthly_rate).quantize(_CENT, ROUND_HALF_UP)
                minimum = _compute_minimum(tranche)

                # Apply extra payment to priority account's tranches first
                extra_for_tranche = Decimal("0")
                is_priority = acct.account_id == priority_account.account_id
                if is_priority and available_extra > Decimal("0"):
                    extra_for_tranche = available_extra
                    available_extra = Decimal("0")

                payment_attempt = minimum + extra_for_tranche
                # Clamp to payoff amount
                payoff_amount = bal + interest
                payment = min(payment_attempt, payoff_amount)
                payment = max(payment, min(minimum, payoff_amount))

                principal_paid = payment - interest
                if principal_paid < Decimal("0"):
                    principal_paid = Decimal("0")

                new_bal = (bal - principal_paid).quantize(_CENT, ROUND_HALF_UP)
                if new_bal < Decimal("0"):
                    new_bal = Decimal("0")
                    principal_paid = bal
                    payment = interest + principal_paid

                total_opening += bal
                total_payment += payment
                total_principal += principal_paid
                total_interest += interest
                total_closing += new_bal
                balances[tranche.balance_id] = new_bal

            is_payoff = total_closing <= Decimal("0")

            # If account just paid off and snowball_flow, redirect its minimum
            if is_payoff and snowball_flow:
                acct_minimum = acct.total_minimum
                redirected_extra += acct_minimum

            account_summaries[acct.account_id] = (
                total_opening,
                total_payment,
                total_principal,
                total_interest,
                is_payoff,
            )

        # Recalculate ordered based on remaining balances for next iteration's priority
        ordered = _sort_accounts(
            [
                AccountState(
                    account_id=a.account_id,
                    tranches=[
                        AccountTranche(
                            balance_id=t.balance_id,
                            account_id=t.account_id,
                            principal=balances.get(t.balance_id, Decimal("0")),
                            apr=aprs[t.balance_id],
                            currency=t.currency,
                            minimum_payment=t.minimum_payment,
                        )
                        for t in a.tranches
                    ],
                    currency=a.currency,
                )
                for a in ordered
            ],
            method,
            account_ids_order,
        )

        for acct_id, (
            opening,
            payment,
            principal,
            interest,
            is_payoff,
        ) in account_summaries.items():
            if opening <= Decimal("0"):
                continue
            closing = (opening - principal).quantize(_CENT, ROUND_HALF_UP)
            if closing < Decimal("0"):
                closing = Decimal("0")
            rows.append(
                _PeriodRow(
                    account_id=acct_id,
                    period_date=period_date,
                    opening_balance=opening.quantize(_CENT, ROUND_HALF_UP),
                    currency=currencies[acct_id],
                    payment=payment.quantize(_CENT, ROUND_HALF_UP),
                    principal=principal.quantize(_CENT, ROUND_HALF_UP),
                    interest=interest.quantize(_CENT, ROUND_HALF_UP),
                    closing_balance=closing,
                    is_payoff=is_payoff,
                )
            )

    return rows


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to end of month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar

    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _fetch_account_states(
    session: AsyncSession,
    account_ids: list[uuid.UUID],
    household_id: uuid.UUID,
) -> list[AccountState]:
    """Load DebtAccount + current DebtBalance data via accounts module."""
    states: list[AccountState] = []
    for acct_id in account_ids:
        try:
            da = await accounts_svc.get_debt_annotation(
                session, account_id=acct_id, household_id=household_id
            )
        except accounts_svc.NotFoundError:
            logger.warning("debt_engine.account_not_found", account_id=str(acct_id))
            continue

        # All current balance tranches (effective_to IS NULL)
        result = await session.execute(
            sa.select(DebtBalance).where(
                DebtBalance.debt_account_id == da.id,
                DebtBalance.effective_to.is_(None),
                DebtBalance.archived_at.is_(None),
            )
        )
        balances = list(result.scalars().all())
        if not balances:
            logger.warning("debt_engine.no_balances", account_id=str(acct_id))
            continue

        account_result = await session.execute(sa.select(Account).where(Account.id == acct_id))
        account = account_result.scalar_one_or_none()
        currency = account.currency if account else "USD"

        tranches = [
            AccountTranche(
                balance_id=b.id,
                account_id=acct_id,
                principal=b.principal_balance,
                apr=b.apr,
                currency=b.currency or currency,
                minimum_payment=_compute_minimum(
                    AccountTranche(
                        balance_id=b.id,
                        account_id=acct_id,
                        principal=b.principal_balance,
                        apr=b.apr,
                        currency=b.currency or currency,
                        minimum_payment=Decimal("0"),
                    )
                ),
            )
            for b in balances
        ]
        states.append(AccountState(account_id=acct_id, tranches=tranches, currency=currency))
    return states


# ---------------------------------------------------------------------------
# Plan CRUD (versioned)
# ---------------------------------------------------------------------------


async def create_plan(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    method: DebtPlanMethod,
    monthly_extra_payment: Decimal = Decimal("0"),
    currency: str = "USD",
    snowball_flow: bool = True,
    account_ids: list[uuid.UUID] | None = None,
    effective_from: date | None = None,
) -> DebtPlan:
    """Create the first version of a new debt plan."""
    plan_id = new_uuid()
    eff_from = effective_from or date.today()
    plan = DebtPlan(
        id=plan_id,
        plan_group_id=plan_id,
        household_id=household_id,
        name=name,
        method=str(method),
        monthly_extra_payment=monthly_extra_payment,
        currency=currency.upper(),
        snowball_flow=snowball_flow,
        account_ids=[str(a) for a in (account_ids or [])],
        effective_from=eff_from,
        effective_to=None,
    )
    session.add(plan)
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="debt_plan",
        entity_id=plan_id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
        actor_id=actor_id,
    )
    logger.info("debt_plan.created", plan_id=str(plan_id), household_id=str(household_id))
    return plan


async def get_plan(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> DebtPlan:
    """Return the current (effective_to IS NULL) version of a plan."""
    result = await session.execute(
        sa.select(DebtPlan).where(
            DebtPlan.plan_group_id == plan_group_id,
            DebtPlan.household_id == household_id,
            DebtPlan.effective_to.is_(None),
            DebtPlan.archived_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise NotFoundError("debt plan not found")
    return plan


async def get_active_plan(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of_date: date,
) -> DebtPlan:
    """Return the plan version active on as_of_date."""
    result = await session.execute(
        sa.select(DebtPlan)
        .where(
            DebtPlan.plan_group_id == plan_group_id,
            DebtPlan.household_id == household_id,
            DebtPlan.effective_from <= as_of_date,
            sa.or_(DebtPlan.effective_to.is_(None), DebtPlan.effective_to >= as_of_date),
            DebtPlan.archived_at.is_(None),
        )
        .order_by(DebtPlan.effective_from.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise NotFoundError("no debt plan version active on that date")
    return plan


async def update_plan(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    effective_from: date | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> DebtPlan:
    """Edit a plan by closing the current version and creating a new one."""
    current = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    new_eff_from = effective_from or date.today()

    current.effective_to = new_eff_from - timedelta(days=1)
    await session.flush()

    fields: dict[str, Any] = {
        "name": current.name,
        "method": current.method,
        "monthly_extra_payment": current.monthly_extra_payment,
        "currency": current.currency,
        "snowball_flow": current.snowball_flow,
        "account_ids": list(current.account_ids),
    }
    for k, v in kwargs.items():
        if v is not None and k in fields:
            if k == "account_ids" and isinstance(v, list):
                fields[k] = [str(x) for x in v]  # type: ignore[union-attr]
            elif k == "method" and isinstance(v, DebtPlanMethod):
                fields[k] = str(v)
            elif k == "currency" and isinstance(v, str):
                fields[k] = v.upper()
            else:
                fields[k] = v

    new_version = DebtPlan(
        plan_group_id=plan_group_id,
        household_id=household_id,
        effective_from=new_eff_from,
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
        entity_type="debt_plan",
        entity_id=new_version.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/plan_group_id", "value": str(plan_group_id)}],
        actor_id=actor_id,
    )
    logger.info(
        "debt_plan.updated",
        plan_group_id=str(plan_group_id),
        new_version_id=str(new_version.id),
    )
    return new_version


async def archive_plan(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> DebtPlan:
    """Soft-delete all versions of a plan."""
    result = await session.execute(
        sa.select(DebtPlan).where(
            DebtPlan.plan_group_id == plan_group_id,
            DebtPlan.household_id == household_id,
            DebtPlan.archived_at.is_(None),
        ),
        execution_options={"include_archived": False},
    )
    plans = list(result.scalars().all())
    if not plans:
        raise NotFoundError("debt plan not found")

    now = utcnow()
    for p in plans:
        p.archived_at = now
        p.archived_by = actor_id
    await session.flush()

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="debt_plan",
        entity_id=plan_group_id,
        operation=AuditOperation.ARCHIVE,
        delta=[],
        actor_id=actor_id,
    )
    logger.info("debt_plan.archived", plan_group_id=str(plan_group_id))
    current = next((p for p in plans if p.effective_to is None), plans[0])
    return current


async def list_plans(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[DebtPlan]:
    """Return all current plan versions for a household."""
    result = await session.execute(
        sa.select(DebtPlan)
        .where(
            DebtPlan.household_id == household_id,
            DebtPlan.effective_to.is_(None),
        )
        .order_by(DebtPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def list_plan_history(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[DebtPlan]:
    """Return all versions of a plan, newest effective_from first."""
    result = await session.execute(
        sa.select(DebtPlan)
        .where(
            DebtPlan.plan_group_id == plan_group_id,
            DebtPlan.household_id == household_id,
        )
        .order_by(DebtPlan.effective_from.desc()),
        execution_options={"include_archived": True},
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Schedule computation
# ---------------------------------------------------------------------------


async def compute_schedule(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> DebtPlanSummary:
    """Regenerate DebtPlanSchedule and DebtPlanSummary for the active plan version.

    Idempotent -- deletes existing schedule rows for this plan_id before writing.
    """
    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    method = DebtPlanMethod(plan.method)

    if method == DebtPlanMethod.NONE:
        # No schedule, no recommendations
        summary = await _upsert_summary(
            session,
            plan=plan,
            total_interest=Decimal("0"),
            total_paid=Decimal("0"),
            months=0,
            payoff_date=None,
            savings=Decimal("0"),
        )
        return summary

    account_ids = [uuid.UUID(a) for a in plan.account_ids]
    states = await _fetch_account_states(session, account_ids, household_id)

    rows = simulate_schedule(
        accounts=states,
        method=method,
        monthly_extra_payment=plan.monthly_extra_payment,
        snowball_flow=plan.snowball_flow,
        account_ids_order=account_ids,
        start_date=date.today().replace(day=1),
    )

    # Compute minimums-only baseline for savings calculation
    baseline = _run_minimums_baseline(states, account_ids, plan.currency)

    await session.execute(sa.delete(DebtPlanSchedule).where(DebtPlanSchedule.plan_id == plan.id))
    await session.flush()

    for row in rows:
        sched = DebtPlanSchedule(
            plan_id=plan.id,
            household_id=household_id,
            account_id=row.account_id,
            period_date=row.period_date,
            opening_balance=row.opening_balance,
            currency=row.currency,
            payment=row.payment,
            principal=row.principal,
            interest=row.interest,
            closing_balance=row.closing_balance,
            is_payoff=row.is_payoff,
        )
        session.add(sched)
    await session.flush()

    total_interest = sum((r.interest for r in rows), Decimal("0"))
    total_paid = sum((r.payment for r in rows), Decimal("0"))
    payoff_rows = [r for r in rows if r.is_payoff]
    payoff_date = max((r.period_date for r in payoff_rows), default=None)
    months = len({r.period_date for r in rows})

    savings = (baseline.total_interest - total_interest).quantize(_CENT, ROUND_HALF_UP)

    summary = await _upsert_summary(
        session,
        plan=plan,
        total_interest=total_interest.quantize(_CENT, ROUND_HALF_UP),
        total_paid=total_paid.quantize(_CENT, ROUND_HALF_UP),
        months=months,
        payoff_date=payoff_date,
        savings=savings,
    )

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.SYSTEM,
        actor_source="debt_engine",
        entity_type="debt_plan",
        entity_id=plan.id,
        operation=AuditOperation.APPLY,
        delta=[{"op": "replace", "path": "/schedule_recomputed", "value": True}],
    )
    logger.info(
        "debt_engine.schedule_computed",
        plan_id=str(plan.id),
        rows=len(rows),
        months=months,
        payoff_date=str(payoff_date),
    )
    return summary


def _run_minimums_baseline(
    states: list[AccountState],
    account_ids: list[uuid.UUID],
    currency: str,
) -> BaselineSummary:
    """Simulate minimums-only (no extra payment) for baseline comparison."""
    rows = simulate_schedule(
        accounts=states,
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=Decimal("0"),
        snowball_flow=False,
        account_ids_order=account_ids,
        start_date=date.today().replace(day=1),
    )
    total_interest = sum((r.interest for r in rows), Decimal("0"))
    total_paid = sum((r.payment for r in rows), Decimal("0"))
    payoff_rows = [r for r in rows if r.is_payoff]
    payoff_date = max((r.period_date for r in payoff_rows), default=None)
    months = len({r.period_date for r in rows})
    return BaselineSummary(
        total_interest=total_interest.quantize(_CENT, ROUND_HALF_UP),
        total_paid=total_paid.quantize(_CENT, ROUND_HALF_UP),
        months_to_payoff=months,
        payoff_date=payoff_date,
        currency=currency,
    )


async def compute_minimums_baseline(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> BaselineSummary:
    """Return minimums-only summary for comparison display."""
    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    account_ids = [uuid.UUID(a) for a in plan.account_ids]
    states = await _fetch_account_states(session, account_ids, household_id)
    return _run_minimums_baseline(states, account_ids, plan.currency)


async def _upsert_summary(
    session: AsyncSession,
    *,
    plan: DebtPlan,
    total_interest: Decimal,
    total_paid: Decimal,
    months: int,
    payoff_date: date | None,
    savings: Decimal,
) -> DebtPlanSummary:
    result = await session.execute(
        sa.select(DebtPlanSummary).where(DebtPlanSummary.plan_id == plan.id)
    )
    summary = result.scalar_one_or_none()
    if summary is None:
        summary = DebtPlanSummary(
            plan_id=plan.id,
            total_interest=total_interest,
            currency=plan.currency,
            total_paid=total_paid,
            months_to_payoff=months,
            interest_savings_vs_minimums=savings,
            payoff_date=payoff_date,
        )
        session.add(summary)
    else:
        summary.total_interest = total_interest
        summary.currency = plan.currency
        summary.total_paid = total_paid
        summary.months_to_payoff = months
        summary.interest_savings_vs_minimums = savings
        summary.payoff_date = payoff_date
    await session.flush()
    return summary


# ---------------------------------------------------------------------------
# Schedule / summary retrieval
# ---------------------------------------------------------------------------


@dataclass
class DebtPlanScheduleByAccount:
    account_id: uuid.UUID
    rows: list[DebtPlanSchedule]


async def get_schedule(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[DebtPlanScheduleByAccount]:
    """Return schedule rows grouped by account for the current plan version."""
    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    result = await session.execute(
        sa.select(DebtPlanSchedule)
        .where(DebtPlanSchedule.plan_id == plan.id)
        .order_by(DebtPlanSchedule.account_id, DebtPlanSchedule.period_date)
    )
    all_rows = list(result.scalars().all())

    grouped: dict[uuid.UUID, list[DebtPlanSchedule]] = {}
    for row in all_rows:
        grouped.setdefault(row.account_id, []).append(row)

    return [
        DebtPlanScheduleByAccount(account_id=acct_id, rows=rows)
        for acct_id, rows in grouped.items()
    ]


async def get_summary(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> DebtPlanSummary:
    """Return aggregate summary for the current plan version."""
    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    result = await session.execute(
        sa.select(DebtPlanSummary).where(DebtPlanSummary.plan_id == plan.id)
    )
    summary = result.scalar_one_or_none()
    if summary is None:
        raise NotFoundError("no summary found -- run compute_schedule first")
    return summary


# ---------------------------------------------------------------------------
# Recommendation emission
# ---------------------------------------------------------------------------


async def check_payment_deviation(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    actual_payment: Decimal,
    payment_date: date | None = None,
) -> None:
    """Compare actual payment to scheduled amount; emit Recommendation on deviation."""
    check_date = payment_date or date.today()
    period_date = check_date.replace(day=1)

    result = await session.execute(
        sa.select(DebtPlanSchedule)
        .join(DebtPlan, DebtPlan.id == DebtPlanSchedule.plan_id)
        .where(
            DebtPlan.household_id == household_id,
            DebtPlan.effective_to.is_(None),
            DebtPlan.archived_at.is_(None),
            DebtPlanSchedule.account_id == account_id,
            DebtPlanSchedule.period_date == period_date,
        )
        .order_by(DebtPlan.created_at.desc())
        .limit(1)
    )
    scheduled_row = result.scalar_one_or_none()

    if scheduled_row is None:
        return

    scheduled = scheduled_row.payment
    delta = scheduled - actual_payment

    if abs(delta) < Decimal("1.00"):
        return

    direction = "short" if delta > Decimal("0") else "excess"
    rationale = (
        f"Debt payment for account {account_id} in {period_date.strftime('%B %Y')} "
        f"was {direction} by {abs(delta):.2f} {scheduled_row.currency}. "
        f"Scheduled: {scheduled:.2f}, Actual: {actual_payment:.2f}."
    )

    await rec_svc.create(
        session,
        household_id=household_id,
        source=RecommendationSource.DEBT_ENGINE,
        target_subsystem="debts",
        target_entity_id=account_id,
        proposed_value={
            "account_id": str(account_id),
            "period_date": str(period_date),
            "scheduled_payment": str(scheduled),
            "actual_payment": str(actual_payment),
            "delta": str(delta),
            "direction": direction,
        },
        rationale_text=rationale,
        rationale_data={
            "schedule_row_id": str(scheduled_row.id),
            "currency": scheduled_row.currency,
        },
    )

    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.SYSTEM,
        actor_source="debt_engine",
        entity_type="debt_account",
        entity_id=account_id,
        operation=AuditOperation.APPLY,
        delta=[
            {"op": "add", "path": "/payment_recorded", "value": str(actual_payment)},
            {"op": "add", "path": "/deviation_direction", "value": direction},
        ],
    )


async def recommend_budget_line(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> None:
    """Emit a Recommendation suggesting a monthly debt-service budget line."""
    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)

    result = await session.execute(
        sa.select(DebtPlanSchedule).where(
            DebtPlanSchedule.plan_id == plan.id,
            DebtPlanSchedule.period_date == date.today().replace(day=1),
        )
    )
    rows = list(result.scalars().all())

    if not rows:
        return

    total_monthly = sum((r.payment for r in rows), Decimal("0")).quantize(_CENT, ROUND_HALF_UP)

    await rec_svc.create(
        session,
        household_id=household_id,
        source=RecommendationSource.DEBT_ENGINE,
        target_subsystem="budgets",
        proposed_value={
            "plan_group_id": str(plan_group_id),
            "recommended_monthly_amount": str(total_monthly),
            "currency": plan.currency,
            "budget_line_label": "Debt Service",
        },
        rationale_text=(
            f"Debt plan '{plan.name}' recommends a monthly debt-service budget line "
            f"of {total_monthly:.2f} {plan.currency} based on the current payoff schedule."
        ),
        rationale_data={"plan_id": str(plan.id)},
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Comparison (pure simulation, no DB writes)
# ---------------------------------------------------------------------------


@dataclass
class ComparisonSummary:
    label: str
    total_interest: Decimal
    total_paid: Decimal
    months_to_payoff: int
    payoff_date: date | None
    interest_savings_vs_minimums: Decimal


async def compute_comparison(
    session: AsyncSession,
    *,
    plan_group_id: uuid.UUID,
    household_id: uuid.UUID,
    compare: str,
) -> tuple[ComparisonSummary, ComparisonSummary]:
    """Return (current_summary, compared_summary) for side-by-side comparison.

    compare: 'avalanche' | 'snowball' | 'minimums'
    Raises ValidationError if compare value is not valid.
    """
    valid = {"avalanche", "snowball", "minimums"}
    if compare not in valid:
        raise ValidationError(f"compare must be one of: {', '.join(sorted(valid))}")

    plan = await get_plan(session, plan_group_id=plan_group_id, household_id=household_id)
    db_summary = await get_summary(session, plan_group_id=plan_group_id, household_id=household_id)

    current_item = ComparisonSummary(
        label=f"{plan.method} (current)",
        total_interest=db_summary.total_interest,
        total_paid=db_summary.total_paid,
        months_to_payoff=db_summary.months_to_payoff,
        payoff_date=db_summary.payoff_date,
        interest_savings_vs_minimums=db_summary.interest_savings_vs_minimums,
    )

    account_ids = [uuid.UUID(a) for a in plan.account_ids]
    states = await _fetch_account_states(session, account_ids, household_id)
    baseline = _run_minimums_baseline(states, account_ids, plan.currency)

    if compare == "minimums":
        compared_item = ComparisonSummary(
            label="minimums only",
            total_interest=baseline.total_interest,
            total_paid=baseline.total_paid,
            months_to_payoff=baseline.months_to_payoff,
            payoff_date=baseline.payoff_date,
            interest_savings_vs_minimums=Decimal("0"),
        )
    else:
        alt_method = DebtPlanMethod(compare)
        alt_rows = simulate_schedule(
            accounts=states,
            method=alt_method,
            monthly_extra_payment=plan.monthly_extra_payment,
            snowball_flow=plan.snowball_flow,
            account_ids_order=account_ids,
            start_date=date.today().replace(day=1),
        )
        alt_interest = sum((r.interest for r in alt_rows), Decimal("0")).quantize(
            _CENT, ROUND_HALF_UP
        )
        alt_paid = sum((r.payment for r in alt_rows), Decimal("0")).quantize(_CENT, ROUND_HALF_UP)
        alt_payoff_rows = [r for r in alt_rows if r.is_payoff]
        alt_payoff = max((r.period_date for r in alt_payoff_rows), default=None)
        alt_months = len({r.period_date for r in alt_rows})
        alt_savings = (baseline.total_interest - alt_interest).quantize(_CENT, ROUND_HALF_UP)
        compared_item = ComparisonSummary(
            label=compare,
            total_interest=alt_interest,
            total_paid=alt_paid,
            months_to_payoff=alt_months,
            payoff_date=alt_payoff,
            interest_savings_vs_minimums=alt_savings,
        )

    return current_item, compared_item
