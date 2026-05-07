"""Projections service layer — deterministic forward-projection engine.

Reads from all other modules (accounts, recurrences, budgets, debts, goals, FX)
but NEVER writes to their tables. All output is stored in projections_* tables.

Public interface:
  collect_inputs(household_id, as_of_date)           -> ProjectionInputs
  apply_scenario_overrides(inputs, overrides)         -> ProjectionInputs
  run_projection(household_id, as_of_date,
    horizon_months, scenario_id=None,
    force=False)                                      -> ProjectionResult
  get_balance_curve(household_id, account_ids,
    from_date, to_date, scenario_id=None)             -> list[BalanceCurvePoint]
  get_cashflow_summary(household_id, from_date,
    to_date, period, scenario_id=None)                -> list[CashflowPeriod]
  get_net_worth_curve(household_id, from_date,
    to_date, scenario_id=None)                        -> list[NetWorthPoint]
  invalidate_cache(household_id)                      -> None
  create_scenario(...)                                -> ProjectionScenario
  get_scenario(scenario_id, household_id)             -> ProjectionScenario
  list_scenarios(household_id)                        -> list[ProjectionScenario]
  update_scenario(...)                                -> ProjectionScenario
  archive_scenario(scenario_id, household_id,
    actor_id)                                         -> ProjectionScenario
  run_scenario(scenario_id, household_id, ...)        -> ProjectionResult
  cleanup_transient_scenarios(household_id)           -> int
"""

import hashlib
import json
import uuid
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import UTC, date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import ActorType, AuditEvent, AuditOperation
from app.platform.time import utcnow
from app.projections.enums import (
    BreachType,
    OverrideType,
    ProjectedConfidence,
    ProjectedDirection,
    ProjectedEventType,
    ProjectionRunStatus,
)
from app.projections.models import (
    ProjectedEvent,
    ProjectionBreachEvent,
    ProjectionRun,
    ProjectionScenario,
)

logger = structlog.get_logger(__name__)

_CENT = Decimal("0.01")
_MAX_HORIZON_MONTHS = 60
_BASE_CACHE_TTL_HOURS = 1
_SCENARIO_CACHE_TTL_HOURS = 24


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
# Input data structures
# ---------------------------------------------------------------------------


@dataclass
class AccountSnapshot:
    account_id: uuid.UUID
    name: str
    current_balance: Decimal
    currency: str
    account_type: str
    credit_limit: Decimal | None = None


@dataclass
class RecurrenceInput:
    recurrence_id: uuid.UUID
    account_id: uuid.UUID
    expected_dates: list[date]
    expected_amount: Decimal
    currency: str
    direction: str
    confidence: str
    merchant_name: str | None = None


@dataclass
class BudgetLineInput:
    line_id: uuid.UUID
    planned_amount: Decimal
    currency: str
    category_id: uuid.UUID | None


@dataclass
class BudgetInput:
    budget_group_id: uuid.UUID
    expected_income: Decimal | None
    currency: str
    lines: list[BudgetLineInput] = field(default_factory=lambda: [])


@dataclass
class DebtPaymentEntry:
    period_date: date
    payment: Decimal
    account_id: uuid.UUID


@dataclass
class DebtPlanInput:
    plan_group_id: uuid.UUID
    currency: str
    payments: list[DebtPaymentEntry] = field(default_factory=lambda: [])


@dataclass
class GoalInput:
    goal_id: uuid.UUID
    monthly_contribution: Decimal
    currency: str


@dataclass
class FxRateInput:
    from_currency: str
    to_currency: str
    rate: Decimal


@dataclass
class ProjectionInputs:
    household_id: uuid.UUID
    home_currency: str
    as_of_date: date
    accounts: list[AccountSnapshot]
    recurrences: list[RecurrenceInput]
    budgets: list[BudgetInput]
    debt_plans: list[DebtPlanInput]
    goals: list[GoalInput]
    fx_rates: list[FxRateInput]
    inputs_hash: str = ""

    def canonical_dict(self) -> dict[str, Any]:
        """Serialize to a stable canonical dict for hash computation."""
        return {
            "household_id": str(self.household_id),
            "as_of_date": str(self.as_of_date),
            "accounts": sorted(
                [
                    {
                        "id": str(a.account_id),
                        "balance": str(a.current_balance),
                        "currency": a.currency,
                    }
                    for a in self.accounts
                ],
                key=lambda x: x["id"],
            ),
            "recurrences": sorted(
                [
                    {
                        "id": str(r.recurrence_id),
                        "amount": str(r.expected_amount),
                        "currency": r.currency,
                        "direction": r.direction,
                    }
                    for r in self.recurrences
                ],
                key=lambda x: x["id"],
            ),
            "budgets": sorted(
                [
                    {
                        "id": str(b.budget_group_id),
                        "income": str(b.expected_income),
                        "currency": b.currency,
                        "lines": sorted(
                            [
                                {
                                    "id": str(ln.line_id),
                                    "amount": str(ln.planned_amount),
                                    "currency": ln.currency,
                                }
                                for ln in b.lines
                            ],
                            key=lambda x: x["id"],
                        ),
                    }
                    for b in self.budgets
                ],
                key=lambda x: x["id"],
            ),
            "debt_plans": sorted(
                [
                    {
                        "id": str(dp.plan_group_id),
                        "currency": dp.currency,
                        "entries": len(dp.payments),
                    }
                    for dp in self.debt_plans
                ],
                key=lambda x: x["id"],
            ),
            "goals": sorted(
                [
                    {
                        "id": str(g.goal_id),
                        "monthly": str(g.monthly_contribution),
                        "currency": g.currency,
                    }
                    for g in self.goals
                ],
                key=lambda x: x["id"],
            ),
            "fx_rates": sorted(
                [
                    {
                        "from": r.from_currency,
                        "to": r.to_currency,
                        "rate": str(r.rate),
                    }
                    for r in self.fx_rates
                ],
                key=lambda x: (x["from"], x["to"]),
            ),
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ProjectionResult:
    run: ProjectionRun
    events: list[ProjectedEvent]
    breaches: list[ProjectionBreachEvent]


@dataclass
class BalanceCurvePoint:
    event_date: date
    account_id: uuid.UUID
    balance: Decimal
    currency: str


@dataclass
class CashflowPeriod:
    period_start: date
    period_end: date
    total_income: Decimal
    total_expenses: Decimal
    net_cashflow: Decimal
    currency: str


@dataclass
class NetWorthPoint:
    event_date: date
    net_worth: Decimal
    currency: str


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------


async def _get_household_currency(session: AsyncSession, household_id: uuid.UUID) -> str:
    from app.households.models import Household

    result = await session.execute(
        sa.select(Household.home_currency).where(Household.id == household_id)
    )
    row = result.scalar_one_or_none()
    return row if row else "USD"


async def _get_fx_rates(
    session: AsyncSession,
    as_of_date: date,
    currencies: set[str],
    home_currency: str,
) -> list[FxRateInput]:
    from app.platform.fx import FxRate

    if not currencies or currencies == {home_currency}:
        return []

    foreign = currencies - {home_currency}
    rates: list[FxRateInput] = []

    for fc in foreign:
        result = await session.execute(
            sa.select(FxRate)
            .where(
                FxRate.from_currency == fc,
                FxRate.to_currency == home_currency,
                FxRate.rate_date <= as_of_date,
            )
            .order_by(FxRate.rate_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            rates.append(
                FxRateInput(
                    from_currency=fc,
                    to_currency=home_currency,
                    rate=row.rate,
                )
            )

    return rates


async def collect_inputs(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    as_of_date: date,
    horizon_months: int,
) -> ProjectionInputs:
    """Collect all projection inputs from module service interfaces.

    Called once per run_projection call (before cache check when hash needed,
    or skipped if cache hit by checking existing runs first).
    """
    import app.accounts.service as acct_svc
    import app.budgets.service as budgets_svc
    import app.debts.service as debts_svc
    import app.goals.service as goals_svc
    import app.recurrences.service as rec_svc

    home_currency = await _get_household_currency(session, household_id)

    # --- Accounts ---
    raw_accounts = await acct_svc.list_accounts(session, household_id=household_id)
    accounts: list[AccountSnapshot] = [
        AccountSnapshot(
            account_id=a.id,
            name=a.name,
            current_balance=a.current_balance,
            currency=a.currency,
            account_type=a.account_type,
        )
        for a in raw_accounts
    ]

    # --- Recurrences ---
    horizon_end = _add_months(as_of_date, horizon_months)
    raw_events = await rec_svc.get_expected_events(
        session,
        household_id=household_id,
        from_date=as_of_date + timedelta(days=1),
        to_date=horizon_end,
    )

    rec_inputs: list[RecurrenceInput] = []
    seen_rec_ids: set[uuid.UUID] = set()
    date_map: dict[uuid.UUID, list[date]] = {}
    meta_map: dict[uuid.UUID, dict[str, Any]] = {}
    amount_map: dict[uuid.UUID, Decimal] = {}
    currency_map: dict[uuid.UUID, str] = {}
    strategy_map: dict[uuid.UUID, str] = {}
    merchant_map: dict[uuid.UUID, str | None] = {}
    account_map: dict[uuid.UUID, uuid.UUID] = {}

    for ev in raw_events:
        if ev.recurrence_id not in seen_rec_ids:
            seen_rec_ids.add(ev.recurrence_id)
            date_map[ev.recurrence_id] = []
            amount_map[ev.recurrence_id] = ev.expected_amount
            currency_map[ev.recurrence_id] = ev.currency
            merchant_map[ev.recurrence_id] = ev.merchant_name
            account_map[ev.recurrence_id] = ev.account_id

        effective_date = ev.override_date if ev.override_date is not None else ev.expected_date
        date_map[ev.recurrence_id].append(effective_date)

    raw_recurrences = await rec_svc.list_recurrences(session, household_id=household_id)
    for rec in raw_recurrences:
        strategy_map[rec.id] = rec.expected_amount_strategy
        raw_meta = rec.recurrence_metadata
        meta_map[rec.id] = raw_meta if raw_meta else {}

    for rid in seen_rec_ids:
        strategy = strategy_map.get(rid, "fixed")
        is_income = meta_map.get(rid, {}).get("is_income", False)
        direction = str(ProjectedDirection.CREDIT) if is_income else str(ProjectedDirection.DEBIT)
        confidence = (
            str(ProjectedConfidence.HIGH)
            if strategy == "fixed"
            else str(ProjectedConfidence.MEDIUM)
        )
        rec_inputs.append(
            RecurrenceInput(
                recurrence_id=rid,
                account_id=account_map[rid],
                expected_dates=sorted(date_map[rid]),
                expected_amount=amount_map[rid],
                currency=currency_map[rid],
                direction=direction,
                confidence=confidence,
                merchant_name=merchant_map[rid],
            )
        )

    # --- Budgets ---
    raw_budgets = await budgets_svc.list_budgets(session, household_id=household_id)
    budget_inputs: list[BudgetInput] = []
    for bgt in raw_budgets:
        lines = await budgets_svc.list_budget_lines(
            session,
            budget_group_id=bgt.budget_group_id,
            household_id=household_id,
        )
        budget_inputs.append(
            BudgetInput(
                budget_group_id=bgt.budget_group_id,
                expected_income=bgt.expected_income,
                currency=bgt.currency,
                lines=[
                    BudgetLineInput(
                        line_id=ln.id,
                        planned_amount=ln.planned_amount,
                        currency=ln.currency,
                        category_id=ln.category_id if hasattr(ln, "category_id") else None,
                    )
                    for ln in lines
                    if not ln.archived_at
                ],
            )
        )

    # --- Debt plans ---
    raw_plans = await debts_svc.list_plans(session, household_id=household_id)
    debt_plan_inputs: list[DebtPlanInput] = []

    for plan in raw_plans:
        try:
            schedule_by_account = await debts_svc.get_schedule(
                session,
                plan_group_id=plan.plan_group_id,
                household_id=household_id,
            )
        except Exception:  # noqa: S112
            continue

        payments: list[DebtPaymentEntry] = []
        for sba in schedule_by_account:
            for row in sba.rows:
                if as_of_date < row.period_date <= horizon_end:
                    payments.append(
                        DebtPaymentEntry(
                            period_date=row.period_date,
                            payment=row.payment,
                            account_id=sba.account_id,
                        )
                    )

        debt_plan_inputs.append(
            DebtPlanInput(
                plan_group_id=plan.plan_group_id,
                currency=plan.currency if hasattr(plan, "currency") else home_currency,
                payments=payments,
            )
        )

    # --- Goals ---
    raw_goals = await goals_svc.list_goals(session, household_id=household_id)
    goal_inputs: list[GoalInput] = []
    for goal in raw_goals:
        if goal.target_amount is None or goal.target_amount <= Decimal("0"):
            continue
        if goal.status not in ("active", "paused"):
            continue

        monthly = goal.metadata_.get("monthly_contribution")
        if monthly is not None:
            try:
                monthly_contribution = Decimal(str(monthly)).quantize(_CENT, ROUND_HALF_UP)
            except Exception:
                monthly_contribution = Decimal("0")
        elif goal.target_date is not None and goal.target_date > as_of_date:
            days_remaining = (goal.target_date - as_of_date).days
            months_remaining = max(1, days_remaining // 30)
            monthly_contribution = (goal.target_amount / Decimal(months_remaining)).quantize(
                _CENT, ROUND_HALF_UP
            )
        else:
            continue

        if monthly_contribution > Decimal("0"):
            goal_inputs.append(
                GoalInput(
                    goal_id=goal.id,
                    monthly_contribution=monthly_contribution,
                    currency=goal.currency,
                )
            )

    # --- FX rates ---
    all_currencies: set[str] = {home_currency}
    for a in accounts:
        all_currencies.add(a.currency)
    for r in rec_inputs:
        all_currencies.add(r.currency)
    for b in budget_inputs:
        all_currencies.add(b.currency)

    fx_rates = await _get_fx_rates(session, as_of_date, all_currencies, home_currency)

    inputs = ProjectionInputs(
        household_id=household_id,
        home_currency=home_currency,
        as_of_date=as_of_date,
        accounts=accounts,
        recurrences=rec_inputs,
        budgets=budget_inputs,
        debt_plans=debt_plan_inputs,
        goals=goal_inputs,
        fx_rates=fx_rates,
    )
    inputs.inputs_hash = inputs.compute_hash()
    return inputs


# ---------------------------------------------------------------------------
# Scenario overrides
# ---------------------------------------------------------------------------


def apply_scenario_overrides(
    inputs: ProjectionInputs,
    overrides: list[dict[str, Any]],
) -> ProjectionInputs:
    """Apply scenario override deltas to a ProjectionInputs snapshot.

    Returns a modified copy; the original is not mutated.
    """
    import copy

    result = copy.deepcopy(inputs)

    for override in overrides:
        otype = override.get("type")

        if otype == str(OverrideType.REMOVE_RECURRENCE):
            rid_raw = override.get("recurrence_id")
            if rid_raw:
                rid = uuid.UUID(str(rid_raw))
                result.recurrences = [r for r in result.recurrences if r.recurrence_id != rid]

        elif otype == str(OverrideType.ADD_RECURRENCE):
            rid_raw = override.get("recurrence_id")
            account_raw = override.get("account_id")
            if rid_raw and account_raw:
                rid = uuid.UUID(str(rid_raw))
                acct_id = uuid.UUID(str(account_raw))
                amount = Decimal(str(override.get("amount", "0")))
                currency = str(override.get("currency", result.home_currency))
                cadence = str(override.get("cadence", "monthly"))
                start_raw = override.get("start_date")
                start = (
                    date.fromisoformat(str(start_raw))
                    if start_raw
                    else result.as_of_date + timedelta(days=1)
                )
                horizon_end = _add_months(result.as_of_date, _MAX_HORIZON_MONTHS)
                from app.recurrences.service import generate_expected_dates

                dates = generate_expected_dates(
                    cadence=cadence,
                    start_date=start,
                    end_date=None,
                    expected_day_of_period=None,
                    from_date=result.as_of_date + timedelta(days=1),
                    to_date=horizon_end,
                )
                is_income = bool(override.get("is_income", False))
                result.recurrences.append(
                    RecurrenceInput(
                        recurrence_id=rid,
                        account_id=acct_id,
                        expected_dates=dates,
                        expected_amount=amount,
                        currency=currency,
                        direction=(
                            str(ProjectedDirection.CREDIT)
                            if is_income
                            else str(ProjectedDirection.DEBIT)
                        ),
                        confidence=str(ProjectedConfidence.MEDIUM),
                    )
                )

        elif otype == str(OverrideType.CHANGE_INCOME):
            bid_raw = override.get("budget_id")
            amount_raw = override.get("amount")
            if bid_raw and amount_raw is not None:
                bid = uuid.UUID(str(bid_raw))
                new_income = Decimal(str(amount_raw))
                for b in result.budgets:
                    if b.budget_group_id == bid:
                        b.expected_income = new_income

        elif otype == str(OverrideType.CHANGE_EXTRA_DEBT_PAYMENT):
            pid_raw = override.get("plan_id")
            extra_raw = override.get("extra_payment")
            if pid_raw and extra_raw is not None:
                pid = uuid.UUID(str(pid_raw))
                extra = Decimal(str(extra_raw))
                for dp in result.debt_plans:
                    if dp.plan_group_id == pid:
                        for entry in dp.payments:
                            entry.payment = (entry.payment + extra).quantize(_CENT, ROUND_HALF_UP)

        elif otype == str(OverrideType.CHANGE_GOAL_CONTRIBUTION):
            gid_raw = override.get("goal_id")
            monthly_raw = override.get("monthly_amount")
            if gid_raw and monthly_raw is not None:
                gid = uuid.UUID(str(gid_raw))
                new_monthly = Decimal(str(monthly_raw))
                for g in result.goals:
                    if g.goal_id == gid:
                        g.monthly_contribution = new_monthly

        elif otype == str(OverrideType.CHANGE_ACCOUNT_BALANCE):
            aid_raw = override.get("account_id")
            bal_raw = override.get("balance")
            if aid_raw and bal_raw is not None:
                aid = uuid.UUID(str(aid_raw))
                new_balance = Decimal(str(bal_raw))
                for a in result.accounts:
                    if a.account_id == aid:
                        a.current_balance = new_balance

    result.inputs_hash = result.compute_hash()
    return result


# ---------------------------------------------------------------------------
# Simulation engine (pure — no DB)
# ---------------------------------------------------------------------------


def _add_months(d: date, months: int) -> date:
    """Add a calendar month count to a date, clamping to the last day of the month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _period_months(as_of_date: date, horizon_months: int) -> list[date]:
    """Return a list of first-of-month dates for the projection horizon."""
    months: list[date] = []
    current = as_of_date.replace(day=1) + timedelta(days=32)
    current = current.replace(day=1)
    horizon_end = _add_months(as_of_date, horizon_months)
    while current <= horizon_end:
        months.append(current)
        current = _add_months(current, 1)
    return months


def _default_account_for_household(accounts: list[AccountSnapshot]) -> uuid.UUID | None:
    """Return the first checking/savings account id, or the first account overall."""
    for a in accounts:
        if a.account_type in ("checking", "savings"):
            return a.account_id
    return accounts[0].account_id if accounts else None


def _simulate(
    inputs: ProjectionInputs,
    horizon_months: int,
    run_id: uuid.UUID,
    household_id: uuid.UUID,
) -> tuple[list[ProjectedEvent], list[ProjectionBreachEvent]]:
    """Pure simulation engine. Produces ProjectedEvent and ProjectionBreachEvent lists.

    Day hard-cap: 60 months * 31 days = 1860 iterations max (enforced by caller).
    """
    events: list[ProjectedEvent] = []
    breaches: list[ProjectionBreachEvent] = []
    as_of = inputs.as_of_date
    horizon_end = _add_months(as_of, horizon_months)

    # Running balance per account_id
    balances: dict[uuid.UUID, Decimal] = {a.account_id: a.current_balance for a in inputs.accounts}

    # Track which accounts have already triggered a breach per type to avoid duplicates
    breached: dict[tuple[uuid.UUID, str], bool] = {}

    # Track goal cumulative contributions for goal_reached breach
    goal_cumulative: dict[uuid.UUID, Decimal] = {}

    # Debt: track remaining balances per account (approximate — just payment reduction)
    debt_balances: dict[uuid.UUID, Decimal] = {}
    for dp in inputs.debt_plans:
        for entry in dp.payments:
            if entry.account_id not in debt_balances:
                for a in inputs.accounts:
                    if a.account_id == entry.account_id:
                        debt_balances[entry.account_id] = a.current_balance
                        break

    default_acct = _default_account_for_household(inputs.accounts)

    def _make_event(
        *,
        event_date: date,
        event_type: str,
        amount: Decimal,
        currency: str,
        direction: str,
        confidence: str,
        account_id: uuid.UUID,
        source_id: uuid.UUID | None = None,
        source_type: str | None = None,
        description: str | None = None,
        scenario_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectedEvent:
        from app.platform.ids import new_uuid

        return ProjectedEvent(
            id=new_uuid(),
            household_id=household_id,
            run_id=run_id,
            scenario_id=scenario_id,
            account_id=account_id,
            event_date=event_date,
            event_type=event_type,
            amount=amount,
            currency=currency,
            direction=direction,
            confidence=confidence,
            source_id=source_id,
            source_type=source_type,
            description=description,
            metadata_=metadata or {},
        )

    def _make_breach(
        *,
        breach_type: str,
        breach_date: date,
        amount: Decimal,
        currency: str,
        account_id: uuid.UUID,
        description: str | None = None,
    ) -> ProjectionBreachEvent:
        from app.platform.ids import new_uuid

        return ProjectionBreachEvent(
            id=new_uuid(),
            run_id=run_id,
            household_id=household_id,
            account_id=account_id,
            breach_type=breach_type,
            breach_date=breach_date,
            amount=amount,
            currency=currency,
            description=description,
        )

    def _check_balance_breaches(d: date) -> None:
        for acct in inputs.accounts:
            aid = acct.account_id
            bal = balances.get(aid, acct.current_balance)
            key_neg = (aid, str(BreachType.NEGATIVE_BALANCE))
            if bal < Decimal("0") and not breached.get(key_neg):
                breached[key_neg] = True
                breaches.append(
                    _make_breach(
                        breach_type=str(BreachType.NEGATIVE_BALANCE),
                        breach_date=d,
                        amount=bal.copy_abs(),
                        currency=acct.currency,
                        account_id=aid,
                        description=f"Projected balance goes negative ({bal:.2f})",
                    )
                )

    def _check_debt_free(d: date) -> None:
        all_zero = all(v <= Decimal("0") for v in debt_balances.values())
        if not debt_balances:
            return
        key = (uuid.UUID(int=0), str(BreachType.DEBT_FREE))
        if all_zero and not breached.get(key):
            breached[key] = True
            # Emit one breach with account_id = first debt account
            first_acct = next(iter(debt_balances.keys()))
            breaches.append(
                _make_breach(
                    breach_type=str(BreachType.DEBT_FREE),
                    breach_date=d,
                    amount=Decimal("0"),
                    currency=inputs.home_currency,
                    account_id=first_acct,
                    description="All projected debt balances reach zero",
                )
            )

    # Build a sorted list of (date, callable) events to process
    # We'll generate them upfront then sort by date

    # --- Recurrences ---
    for rec in inputs.recurrences:
        for d in rec.expected_dates:
            if d <= as_of or d > horizon_end:
                continue
            acct_id = rec.account_id
            if acct_id not in balances and default_acct is not None:
                acct_id = default_acct
            etype = (
                str(ProjectedEventType.INCOME)
                if rec.direction == str(ProjectedDirection.CREDIT)
                else str(ProjectedEventType.RECURRENCE)
            )
            events.append(
                _make_event(
                    event_date=d,
                    event_type=etype,
                    amount=rec.expected_amount,
                    currency=rec.currency,
                    direction=rec.direction,
                    confidence=rec.confidence,
                    account_id=acct_id,
                    source_id=rec.recurrence_id,
                    source_type="recurrence",
                    description=rec.merchant_name,
                )
            )

    # --- Budget income + spend (monthly, placed on 1st of each period month) ---
    for period_start in _period_months(as_of, horizon_months):
        if period_start > horizon_end:
            break
        for bgt in inputs.budgets:
            # Income event
            if bgt.expected_income and bgt.expected_income > Decimal("0"):
                acct_id = default_acct
                if acct_id is None:
                    continue
                events.append(
                    _make_event(
                        event_date=period_start,
                        event_type=str(ProjectedEventType.INCOME),
                        amount=bgt.expected_income,
                        currency=bgt.currency,
                        direction=str(ProjectedDirection.CREDIT),
                        confidence=str(ProjectedConfidence.MEDIUM),
                        account_id=acct_id,
                        source_id=bgt.budget_group_id,
                        source_type="budget",
                        description="Projected income",
                    )
                )

            # Budget spend events per line
            for ln in bgt.lines:
                if ln.planned_amount <= Decimal("0"):
                    continue
                acct_id = default_acct
                if acct_id is None:
                    continue
                events.append(
                    _make_event(
                        event_date=period_start,
                        event_type=str(ProjectedEventType.BUDGET_SPEND),
                        amount=ln.planned_amount,
                        currency=ln.currency,
                        direction=str(ProjectedDirection.DEBIT),
                        confidence=str(ProjectedConfidence.LOW),
                        account_id=acct_id,
                        source_id=ln.line_id,
                        source_type="budget_line",
                        description=None,
                    )
                )

    # --- Debt payments ---
    for dp in inputs.debt_plans:
        for entry in dp.payments:
            if entry.period_date <= as_of or entry.period_date > horizon_end:
                continue
            acct_id = entry.account_id
            if acct_id not in balances and default_acct is not None:
                acct_id = default_acct
            events.append(
                _make_event(
                    event_date=entry.period_date,
                    event_type=str(ProjectedEventType.DEBT_PAYMENT),
                    amount=entry.payment,
                    currency=dp.currency,
                    direction=str(ProjectedDirection.DEBIT),
                    confidence=str(ProjectedConfidence.HIGH),
                    account_id=acct_id,
                    source_id=dp.plan_group_id,
                    source_type="debt_plan",
                    description="Projected debt payment",
                )
            )

    # --- Goal contributions (monthly, 1st of month) ---
    for period_start in _period_months(as_of, horizon_months):
        if period_start > horizon_end:
            break
        for goal in inputs.goals:
            if goal.monthly_contribution <= Decimal("0"):
                continue
            acct_id = default_acct
            if acct_id is None:
                continue
            events.append(
                _make_event(
                    event_date=period_start,
                    event_type=str(ProjectedEventType.GOAL_CONTRIBUTION),
                    amount=goal.monthly_contribution,
                    currency=goal.currency,
                    direction=str(ProjectedDirection.DEBIT),
                    confidence=str(ProjectedConfidence.MEDIUM),
                    account_id=acct_id,
                    source_id=goal.goal_id,
                    source_type="goal",
                    description="Projected goal contribution",
                )
            )
            # Track cumulative for goal_reached breach
            if goal.goal_id not in goal_cumulative:
                goal_cumulative[goal.goal_id] = Decimal("0")
            goal_cumulative[goal.goal_id] += goal.monthly_contribution

    # --- Sort events by date and apply balance updates + breach checks ---
    events.sort(key=lambda e: e.event_date)

    # Reset balance tracking and walk events in order
    balances = {a.account_id: a.current_balance for a in inputs.accounts}
    goal_cumulative = {}

    for evt in events:
        aid = evt.account_id
        if aid not in balances:
            balances[aid] = Decimal("0")

        if evt.direction == str(ProjectedDirection.DEBIT):
            balances[aid] -= evt.amount
        else:
            balances[aid] += evt.amount

        # Update debt balance tracking
        if evt.event_type == str(ProjectedEventType.DEBT_PAYMENT):
            if aid in debt_balances:
                debt_balances[aid] = max(Decimal("0"), debt_balances[aid] - evt.amount.copy_abs())

        # Update goal cumulative and check goal_reached
        if evt.event_type == str(ProjectedEventType.GOAL_CONTRIBUTION) and evt.source_id:
            gid = evt.source_id
            goal_cumulative[gid] = goal_cumulative.get(gid, Decimal("0")) + evt.amount
            for goal in inputs.goals:
                if goal.goal_id != gid:
                    continue

        _check_balance_breaches(evt.event_date)

    _check_debt_free(horizon_end)

    return events, breaches


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


async def _find_cached_run(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    inputs_hash: str,
    as_of_date: date,
    horizon_months: int,
    scenario_id: uuid.UUID | None,
) -> ProjectionRun | None:
    from datetime import datetime

    now = datetime.now(tz=UTC)
    result = await session.execute(
        sa.select(ProjectionRun).where(
            ProjectionRun.household_id == household_id,
            ProjectionRun.inputs_hash == inputs_hash,
            ProjectionRun.as_of_date == as_of_date,
            ProjectionRun.horizon_months == horizon_months,
            ProjectionRun.scenario_id == scenario_id,
            ProjectionRun.status == str(ProjectionRunStatus.COMPLETE),
            ProjectionRun.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def _load_run_events(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> list[ProjectedEvent]:
    result = await session.execute(
        sa.select(ProjectedEvent)
        .where(ProjectedEvent.run_id == run_id)
        .order_by(ProjectedEvent.event_date)
    )
    return list(result.scalars().all())


async def load_run_breaches(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> list[ProjectionBreachEvent]:
    result = await session.execute(
        sa.select(ProjectionBreachEvent)
        .where(ProjectionBreachEvent.run_id == run_id)
        .order_by(ProjectionBreachEvent.breach_date)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Core run_projection
# ---------------------------------------------------------------------------


async def run_projection(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    as_of_date: date,
    horizon_months: int = 12,
    scenario_id: uuid.UUID | None = None,
    force: bool = False,
) -> ProjectionResult:
    """Compute or return a cached projection for the household.

    If a matching cached run exists (same inputs_hash, as_of_date,
    horizon_months, scenario_id, not expired), returns it directly.
    Otherwise runs the simulation, persists results, and returns them.
    """
    if horizon_months < 1 or horizon_months > _MAX_HORIZON_MONTHS:
        raise ValidationError(
            f"horizon_months must be between 1 and {_MAX_HORIZON_MONTHS}, got {horizon_months}"
        )

    inputs = await collect_inputs(
        session,
        household_id=household_id,
        as_of_date=as_of_date,
        horizon_months=horizon_months,
    )

    if scenario_id is not None:
        scenario = await get_scenario(session, scenario_id=scenario_id, household_id=household_id)
        overrides: list[Any] = scenario.overrides or []
        inputs = apply_scenario_overrides(inputs, overrides)

    if not force:
        cached = await _find_cached_run(
            session,
            household_id=household_id,
            inputs_hash=inputs.inputs_hash,
            as_of_date=as_of_date,
            horizon_months=horizon_months,
            scenario_id=scenario_id,
        )
        if cached is not None:
            events = await _load_run_events(session, cached.id)
            breaches = await load_run_breaches(session, cached.id)
            logger.info(
                "projection.cache_hit",
                household_id=str(household_id),
                run_id=str(cached.id),
            )
            return ProjectionResult(run=cached, events=events, breaches=breaches)

    from datetime import datetime

    from app.platform.ids import new_uuid

    now = datetime.now(tz=UTC)
    ttl_hours = _SCENARIO_CACHE_TTL_HOURS if scenario_id is not None else _BASE_CACHE_TTL_HOURS
    from datetime import timedelta as _td

    expires = now + _td(hours=ttl_hours)

    run_id = new_uuid()
    run = ProjectionRun(
        id=run_id,
        household_id=household_id,
        scenario_id=scenario_id,
        as_of_date=as_of_date,
        horizon_months=horizon_months,
        inputs_hash=inputs.inputs_hash,
        computed_at=now,
        expires_at=expires,
        status=str(ProjectionRunStatus.PENDING),
    )
    session.add(run)
    await session.flush()

    try:
        sim_events, sim_breaches = _simulate(
            inputs,
            horizon_months=horizon_months,
            run_id=run_id,
            household_id=household_id,
        )

        # Delete prior events for same household + scenario + as_of_date
        await session.execute(
            sa.delete(ProjectedEvent).where(
                ProjectedEvent.household_id == household_id,
                ProjectedEvent.scenario_id == scenario_id,
                ProjectedEvent.event_date >= as_of_date,
                ProjectedEvent.run_id != run_id,
            )
        )

        for evt in sim_events:
            session.add(evt)
        for breach in sim_breaches:
            session.add(breach)

        run.status = str(ProjectionRunStatus.COMPLETE)
        await session.flush()

        logger.info(
            "projection.complete",
            household_id=str(household_id),
            run_id=str(run_id),
            events=len(sim_events),
            breaches=len(sim_breaches),
        )
        return ProjectionResult(run=run, events=sim_events, breaches=sim_breaches)

    except Exception as exc:
        run.status = str(ProjectionRunStatus.FAILED)
        await session.flush()
        logger.error(
            "projection.failed",
            household_id=str(household_id),
            run_id=str(run_id),
            error=str(exc),
        )
        raise


# ---------------------------------------------------------------------------
# Aggregated views
# ---------------------------------------------------------------------------


async def latest_run(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    scenario_id: uuid.UUID | None,
) -> ProjectionRun | None:
    result = await session.execute(
        sa.select(ProjectionRun)
        .where(
            ProjectionRun.household_id == household_id,
            ProjectionRun.scenario_id == scenario_id,
            ProjectionRun.status == str(ProjectionRunStatus.COMPLETE),
        )
        .order_by(ProjectionRun.computed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_balance_curve(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_ids: list[uuid.UUID],
    from_date: date,
    to_date: date,
    scenario_id: uuid.UUID | None = None,
) -> list[BalanceCurvePoint]:
    """Compute running balance per account per day from projected events.

    Starts from the account's current_balance as of the most recent run's
    as_of_date and walks forward through events in date order.
    """
    import app.accounts.service as acct_svc

    run = await latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []

    stmt = (
        sa.select(ProjectedEvent)
        .where(
            ProjectedEvent.run_id == run.id,
            ProjectedEvent.account_id.in_(account_ids),
            ProjectedEvent.event_date <= to_date,
        )
        .order_by(ProjectedEvent.event_date)
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Seed starting balances
    accounts = await acct_svc.list_accounts(session, household_id=household_id)
    account_currency_map: dict[uuid.UUID, str] = {}
    balances: dict[uuid.UUID, Decimal] = {}
    for a in accounts:
        if a.id in account_ids:
            balances[a.id] = a.current_balance
            account_currency_map[a.id] = a.currency

    points: list[BalanceCurvePoint] = []

    for evt in events:
        if evt.event_date < from_date:
            # Apply but don't emit a point
            aid = evt.account_id
            if aid not in balances:
                balances[aid] = Decimal("0")
            if evt.direction == str(ProjectedDirection.DEBIT):
                balances[aid] -= evt.amount
            else:
                balances[aid] += evt.amount
            continue

        # Emit a point for each date-account combo as balance updates
        aid = evt.account_id
        if aid not in balances:
            balances[aid] = Decimal("0")
        if evt.direction == str(ProjectedDirection.DEBIT):
            balances[aid] -= evt.amount
        else:
            balances[aid] += evt.amount

        points.append(
            BalanceCurvePoint(
                event_date=evt.event_date,
                account_id=aid,
                balance=balances[aid],
                currency=account_currency_map.get(aid, "USD"),
            )
        )

    return points


async def get_cashflow_summary(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    from_date: date,
    to_date: date,
    period: str = "monthly",
    scenario_id: uuid.UUID | None = None,
) -> list[CashflowPeriod]:
    """Aggregate projected events into income/expense periods."""
    run = await latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []

    result = await session.execute(
        sa.select(ProjectedEvent)
        .where(
            ProjectedEvent.run_id == run.id,
            ProjectedEvent.event_date >= from_date,
            ProjectedEvent.event_date <= to_date,
        )
        .order_by(ProjectedEvent.event_date)
    )
    events = list(result.scalars().all())

    if period == "weekly":

        def _bucket(d: date) -> tuple[date, date]:
            monday = d - timedelta(days=d.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
    else:

        def _bucket(d: date) -> tuple[date, date]:
            first = d.replace(day=1)
            last_day = monthrange(d.year, d.month)[1]
            return first, d.replace(day=last_day)

    buckets: dict[tuple[date, date], dict[str, Decimal]] = {}
    for evt in events:
        key = _bucket(evt.event_date)
        if key not in buckets:
            buckets[key] = {"income": Decimal("0"), "expenses": Decimal("0")}
        if evt.direction == str(ProjectedDirection.CREDIT):
            buckets[key]["income"] += evt.amount
        else:
            buckets[key]["expenses"] += evt.amount

    return [
        CashflowPeriod(
            period_start=k[0],
            period_end=k[1],
            total_income=v["income"],
            total_expenses=v["expenses"],
            net_cashflow=v["income"] - v["expenses"],
            currency="USD",
        )
        for k, v in sorted(buckets.items())
    ]


async def get_net_worth_curve(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    from_date: date,
    to_date: date,
    scenario_id: uuid.UUID | None = None,
) -> list[NetWorthPoint]:
    """Compute household net worth curve with FX conversion to home_currency."""
    import app.accounts.service as acct_svc

    run = await latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []

    home_currency = await _get_household_currency(session, household_id)
    accounts = await acct_svc.list_accounts(session, household_id=household_id)

    account_ids = [a.id for a in accounts]
    account_currency: dict[uuid.UUID, str] = {a.id: a.currency for a in accounts}
    balances: dict[uuid.UUID, Decimal] = {a.id: a.current_balance for a in accounts}

    # Get FX rates for conversion
    all_currencies: set[str] = {a.currency for a in accounts}
    fx_inputs = await _get_fx_rates(session, run.as_of_date, all_currencies, home_currency)
    fx_map: dict[str, Decimal] = {r.from_currency: r.rate for r in fx_inputs}

    def _to_home(amount: Decimal, currency: str) -> Decimal:
        if currency == home_currency:
            return amount
        rate = fx_map.get(currency)
        if rate is None:
            return amount
        return (amount * rate).quantize(_CENT, ROUND_HALF_UP)

    result = await session.execute(
        sa.select(ProjectedEvent)
        .where(
            ProjectedEvent.run_id == run.id,
            ProjectedEvent.account_id.in_(account_ids),
            ProjectedEvent.event_date <= to_date,
        )
        .order_by(ProjectedEvent.event_date)
    )
    events = list(result.scalars().all())

    points: list[NetWorthPoint] = []
    last_emitted_date: date | None = None

    for evt in events:
        aid = evt.account_id
        if aid not in balances:
            balances[aid] = Decimal("0")
        if evt.direction == str(ProjectedDirection.DEBIT):
            balances[aid] -= evt.amount
        else:
            balances[aid] += evt.amount

        if evt.event_date < from_date:
            continue

        if evt.event_date != last_emitted_date:
            nw = sum(
                (
                    _to_home(bal, account_currency.get(aid, home_currency))
                    for aid, bal in balances.items()
                ),
                Decimal("0"),
            )
            points.append(
                NetWorthPoint(
                    event_date=evt.event_date,
                    net_worth=nw,
                    currency=home_currency,
                )
            )
            last_emitted_date = evt.event_date

    return points


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


async def invalidate_cache(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> None:
    """Expire all projection runs for a household.

    Called by domain event handlers when any input changes (new transaction,
    budget edit, debt payment, goal contribution, recurrence change).
    """
    from datetime import datetime

    now = datetime.now(tz=UTC)
    await session.execute(
        sa.update(ProjectionRun)
        .where(ProjectionRun.household_id == household_id)
        .values(expires_at=now)
    )
    logger.info("projection.cache_invalidated", household_id=str(household_id))


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------


async def create_scenario(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    overrides: list[dict[str, Any]] | None = None,
    saved: bool = False,
) -> ProjectionScenario:
    """Create a new what-if scenario (saved or transient)."""
    from app.platform.ids import new_uuid

    scenario = ProjectionScenario(
        id=new_uuid(),
        household_id=household_id,
        name=name,
        overrides=overrides or [],
        saved=saved,
    )
    session.add(scenario)
    await session.flush()

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="projection_scenario",
            entity_id=scenario.id,
            operation=str(AuditOperation.CREATE),
            delta=[{"op": "add", "path": "/name", "value": name or ""}],
        )
    )
    await session.flush()
    logger.info(
        "projection.scenario.created",
        scenario_id=str(scenario.id),
        saved=saved,
    )
    return scenario


async def get_scenario(
    session: AsyncSession,
    *,
    scenario_id: uuid.UUID,
    household_id: uuid.UUID,
) -> ProjectionScenario:
    """Return scenario scoped to household. Raises NotFoundError if absent."""
    result = await session.execute(
        sa.select(ProjectionScenario).where(
            ProjectionScenario.id == scenario_id,
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.archived_at.is_(None),
        )
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise NotFoundError("scenario not found")
    return scenario


async def list_scenarios(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[ProjectionScenario]:
    """Return saved scenarios for a household."""
    result = await session.execute(
        sa.select(ProjectionScenario)
        .where(
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.saved.is_(True),
            ProjectionScenario.archived_at.is_(None),
        )
        .order_by(ProjectionScenario.created_at.desc())
    )
    return list(result.scalars().all())


async def update_scenario(
    session: AsyncSession,
    *,
    scenario_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    saved: bool | None = None,
) -> ProjectionScenario:
    """Update mutable fields on a scenario."""
    scenario = await get_scenario(session, scenario_id=scenario_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    if name is not None and name != scenario.name:
        delta.append({"op": "replace", "path": "/name", "value": name})
        scenario.name = name
    if saved is not None and saved != scenario.saved:
        delta.append({"op": "replace", "path": "/saved", "value": saved})
        scenario.saved = saved

    await session.flush()

    if delta:
        session.add(
            AuditEvent(
                actor_type=str(ActorType.USER),
                actor_id=actor_id,
                actor_source="user_action",
                household_id=household_id,
                entity_type="projection_scenario",
                entity_id=scenario_id,
                operation=str(AuditOperation.UPDATE),
                delta=delta,
            )
        )
        await session.flush()

    return scenario


async def archive_scenario(
    session: AsyncSession,
    *,
    scenario_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ProjectionScenario:
    """Soft-delete a scenario."""
    scenario = await get_scenario(session, scenario_id=scenario_id, household_id=household_id)
    now = utcnow()
    scenario.archived_at = now
    scenario.archived_by = actor_id
    await session.flush()

    session.add(
        AuditEvent(
            actor_type=str(ActorType.USER),
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="projection_scenario",
            entity_id=scenario_id,
            operation=str(AuditOperation.ARCHIVE),
            delta=[],
        )
    )
    await session.flush()
    logger.info("projection.scenario.archived", scenario_id=str(scenario_id))
    return scenario


async def run_scenario(
    session: AsyncSession,
    *,
    scenario_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of_date: date,
    horizon_months: int = 12,
    force: bool = False,
) -> ProjectionResult:
    """(Re)compute a scenario projection and update base_run_id on the scenario."""
    result = await run_projection(
        session,
        household_id=household_id,
        as_of_date=as_of_date,
        horizon_months=horizon_months,
        scenario_id=scenario_id,
        force=force,
    )
    scenario = await get_scenario(session, scenario_id=scenario_id, household_id=household_id)
    scenario.base_run_id = result.run.id
    await session.flush()
    return result


# ---------------------------------------------------------------------------
# Cleanup job helpers
# ---------------------------------------------------------------------------


async def cleanup_transient_scenarios(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> int:
    """Delete unsaved scenarios older than 24 hours. Returns count deleted."""
    from datetime import datetime, timedelta

    cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
    result = await session.execute(
        sa.select(ProjectionScenario).where(
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.saved.is_(False),
            ProjectionScenario.archived_at.is_(None),
            ProjectionScenario.created_at < cutoff,
        )
    )
    scenarios = list(result.scalars().all())
    count = len(scenarios)
    for s in scenarios:
        await session.delete(s)
    await session.flush()
    return count


# ---------------------------------------------------------------------------
# Calendar events view
# ---------------------------------------------------------------------------


async def get_calendar_events(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    from_date: date,
    to_date: date,
    scenario_id: uuid.UUID | None = None,
) -> list[ProjectedEvent]:
    """Return projected events formatted for calendar consumption.

    Returns events in date order within the window, with confidence levels
    preserved for the UI to render appropriately.
    """
    run = await latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []

    result = await session.execute(
        sa.select(ProjectedEvent)
        .where(
            ProjectedEvent.run_id == run.id,
            ProjectedEvent.event_date >= from_date,
            ProjectedEvent.event_date <= to_date,
        )
        .order_by(ProjectedEvent.event_date)
    )
    return list(result.scalars().all())
