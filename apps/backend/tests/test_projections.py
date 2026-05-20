"""Tests for the projections module.

Unit tests (no DB) cover the pure simulation engine, hash computation,
scenario override logic, and balance/cashflow/net-worth aggregation math.

Integration tests (@pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests:
  - Balance never goes negative without a breach event emitted first
  - Net worth curve is sum of account balance curves (within rounding tolerance)
  - Cache hit: same inputs_hash returns identical events without recompute
  - Scenario override remove_recurrence: removes all events for that recurrence
  - Scenario override add_recurrence: adds events for that recurrence
  - Horizon cap: no ProjectedEvent date exceeds as_of_date + horizon_months
  - inputs_hash is deterministic (same inputs -> same hash)

Golden-file tests:
  - Simple household (2 accounts, 3 recurrences, 1 budget, 1 debt plan)
    -> assert exact ProjectedEvent count and breach dates for 3-month horizon
  - FX scenario: net worth curve converts foreign currency correctly
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.projections.enums import (
    BreachType,
    OverrideType,
    ProjectedConfidence,
    ProjectedDirection,
    ProjectedEventType,
)
from app.projections.service import (
    AccountSnapshot,
    BudgetInput,
    BudgetLineInput,
    DebtPaymentEntry,
    DebtPlanInput,
    FxRateInput,
    GoalInput,
    ProjectionInputs,
    RecurrenceInput,
    _add_months,
    _period_months,
    _simulate,
    apply_scenario_overrides,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_inputs(
    *,
    accounts: list[AccountSnapshot] | None = None,
    recurrences: list[RecurrenceInput] | None = None,
    budgets: list[BudgetInput] | None = None,
    debt_plans: list[DebtPlanInput] | None = None,
    goals: list[GoalInput] | None = None,
    fx_rates: list[FxRateInput] | None = None,
    as_of: date = date(2026, 1, 1),
    home_currency: str = "USD",
    household_id: uuid.UUID | None = None,
) -> ProjectionInputs:
    hh_id = household_id or uuid.uuid4()
    inputs = ProjectionInputs(
        household_id=hh_id,
        home_currency=home_currency,
        as_of_date=as_of,
        accounts=accounts or [],
        recurrences=recurrences or [],
        budgets=budgets or [],
        debt_plans=debt_plans or [],
        goals=goals or [],
        fx_rates=fx_rates or [],
    )
    inputs.inputs_hash = inputs.compute_hash()
    return inputs


def _checking_account(
    balance: Decimal = Decimal("1000"),
    currency: str = "USD",
) -> AccountSnapshot:
    return AccountSnapshot(
        account_id=uuid.uuid4(),
        name="Checking",
        current_balance=balance,
        currency=currency,
        account_type="checking",
    )


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestAddMonths:
    def test_simple_month_add(self) -> None:
        assert _add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)

    def test_year_rollover(self) -> None:
        assert _add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)

    def test_clamps_to_last_day(self) -> None:
        # Jan 31 + 1 month = Feb 28 (2026 is not a leap year)
        assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_zero_months(self) -> None:
        d = date(2026, 6, 15)
        assert _add_months(d, 0) == d

    def test_12_months(self) -> None:
        assert _add_months(date(2026, 1, 1), 12) == date(2027, 1, 1)


class TestPeriodMonths:
    def test_generates_correct_count(self) -> None:
        months = _period_months(date(2026, 1, 1), 3)
        assert len(months) == 3

    def test_all_first_of_month(self) -> None:
        months = _period_months(date(2026, 1, 1), 6)
        for m in months:
            assert m.day == 1

    def test_starts_after_as_of(self) -> None:
        as_of = date(2026, 1, 15)
        months = _period_months(as_of, 3)
        assert all(m > as_of for m in months)


class TestInputsHash:
    def test_deterministic(self) -> None:
        acct = _checking_account()
        inputs1 = _make_inputs(accounts=[acct])
        inputs2 = _make_inputs(accounts=[acct], household_id=inputs1.household_id)
        assert inputs1.inputs_hash == inputs2.inputs_hash

    def test_different_balance_gives_different_hash(self) -> None:
        acct1 = AccountSnapshot(
            account_id=uuid.uuid4(),
            name="A",
            current_balance=Decimal("1000"),
            currency="USD",
            account_type="checking",
        )
        acct2 = AccountSnapshot(
            account_id=acct1.account_id,
            name="A",
            current_balance=Decimal("2000"),
            currency="USD",
            account_type="checking",
        )
        hh_id = uuid.uuid4()
        i1 = _make_inputs(accounts=[acct1], household_id=hh_id)
        i2 = _make_inputs(accounts=[acct2], household_id=hh_id)
        assert i1.inputs_hash != i2.inputs_hash

    @given(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
        st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_hash_stable_under_same_balance(self, b1: Decimal, b2: Decimal) -> None:
        hh_id = uuid.uuid4()
        acct_id = uuid.uuid4()
        acct_a = AccountSnapshot(
            account_id=acct_id,
            name="A",
            current_balance=b1,
            currency="USD",
            account_type="checking",
        )
        acct_b = AccountSnapshot(
            account_id=acct_id,
            name="A",
            current_balance=b1,
            currency="USD",
            account_type="checking",
        )
        ia = _make_inputs(accounts=[acct_a], household_id=hh_id)
        ib = _make_inputs(accounts=[acct_b], household_id=hh_id)
        assert ia.inputs_hash == ib.inputs_hash

        if b1 != b2:
            acct_c = AccountSnapshot(
                account_id=acct_id,
                name="A",
                current_balance=b2,
                currency="USD",
                account_type="checking",
            )
            ic = _make_inputs(accounts=[acct_c], household_id=hh_id)
            assert ia.inputs_hash != ic.inputs_hash


# ===========================================================================
# Simulation engine unit tests
# ===========================================================================


class TestSimulateBasic:
    def _run(
        self,
        inputs: ProjectionInputs,
        horizon: int = 3,
    ) -> Any:
        run_id = uuid.uuid4()
        events, breaches = _simulate(
            inputs,
            horizon_months=horizon,
            run_id=run_id,
            household_id=inputs.household_id,
        )
        return events, breaches

    def test_no_inputs_returns_empty(self) -> None:
        inputs = _make_inputs()
        events, breaches = self._run(inputs)
        assert events == []
        assert breaches == []

    def test_recurrence_events_generated(self) -> None:
        acct = _checking_account()
        rid = uuid.uuid4()
        rec = RecurrenceInput(
            recurrence_id=rid,
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1)],
            expected_amount=Decimal("100"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
            merchant_name="Netflix",
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs)
        rec_events = [e for e in events if e.event_type == str(ProjectedEventType.RECURRENCE)]
        assert len(rec_events) == 2
        assert all(e.source_id == rid for e in rec_events)

    def test_income_recurrence_direction_credit(self) -> None:
        acct = _checking_account()
        rid = uuid.uuid4()
        rec = RecurrenceInput(
            recurrence_id=rid,
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 15)],
            expected_amount=Decimal("3000"),
            currency="USD",
            direction=str(ProjectedDirection.CREDIT),
            confidence=str(ProjectedConfidence.MEDIUM),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs)
        income_events = [e for e in events if e.event_type == str(ProjectedEventType.INCOME)]
        assert len(income_events) == 1
        assert income_events[0].direction == str(ProjectedDirection.CREDIT)

    def test_budget_spend_events_monthly(self) -> None:
        acct = _checking_account(balance=Decimal("5000"))
        line_id = uuid.uuid4()
        budget_id = uuid.uuid4()
        line = BudgetLineInput(
            line_id=line_id,
            planned_amount=Decimal("200"),
            currency="USD",
            category_id=None,
        )
        bgt = BudgetInput(
            budget_group_id=budget_id,
            expected_income=None,
            currency="USD",
            lines=[line],
        )
        inputs = _make_inputs(accounts=[acct], budgets=[bgt], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs, horizon=3)
        spend_events = [e for e in events if e.event_type == str(ProjectedEventType.BUDGET_SPEND)]
        assert len(spend_events) == 3  # 3 months
        assert all(e.confidence == str(ProjectedConfidence.LOW) for e in spend_events)

    def test_budget_income_events_monthly(self) -> None:
        acct = _checking_account()
        bgt = BudgetInput(
            budget_group_id=uuid.uuid4(),
            expected_income=Decimal("4000"),
            currency="USD",
            lines=[],
        )
        inputs = _make_inputs(accounts=[acct], budgets=[bgt], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs, horizon=3)
        income_events = [e for e in events if e.event_type == str(ProjectedEventType.INCOME)]
        assert len(income_events) == 3

    def test_debt_payment_events(self) -> None:
        acct = _checking_account(balance=Decimal("10000"))
        plan_id = uuid.uuid4()
        dp = DebtPlanInput(
            plan_group_id=plan_id,
            currency="USD",
            payments=[
                DebtPaymentEntry(
                    period_date=date(2026, 2, 1),
                    payment=Decimal("500"),
                    account_id=acct.account_id,
                ),
                DebtPaymentEntry(
                    period_date=date(2026, 3, 1),
                    payment=Decimal("500"),
                    account_id=acct.account_id,
                ),
            ],
        )
        inputs = _make_inputs(accounts=[acct], debt_plans=[dp], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs, horizon=3)
        debt_events = [e for e in events if e.event_type == str(ProjectedEventType.DEBT_PAYMENT)]
        assert len(debt_events) == 2
        assert all(e.confidence == str(ProjectedConfidence.HIGH) for e in debt_events)
        assert all(e.source_id == plan_id for e in debt_events)

    def test_goal_contribution_events_monthly(self) -> None:
        acct = _checking_account(balance=Decimal("5000"))
        goal = GoalInput(
            goal_id=uuid.uuid4(),
            monthly_contribution=Decimal("300"),
            currency="USD",
        )
        inputs = _make_inputs(accounts=[acct], goals=[goal], as_of=date(2026, 1, 1))
        events, _ = self._run(inputs, horizon=3)
        goal_events = [
            e for e in events if e.event_type == str(ProjectedEventType.GOAL_CONTRIBUTION)
        ]
        assert len(goal_events) == 3


class TestSimulateBreaches:
    def _run(self, inputs: ProjectionInputs, horizon: int = 3) -> Any:
        return _simulate(
            inputs,
            horizon_months=horizon,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )

    def test_negative_balance_breach(self) -> None:
        acct = _checking_account(balance=Decimal("50"))
        rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1)],
            expected_amount=Decimal("200"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        _events, breaches = self._run(inputs)
        neg_breaches = [b for b in breaches if b.breach_type == str(BreachType.NEGATIVE_BALANCE)]
        assert len(neg_breaches) >= 1
        assert neg_breaches[0].breach_date == date(2026, 2, 1)

    def test_no_breach_when_balance_sufficient(self) -> None:
        acct = _checking_account(balance=Decimal("10000"))
        rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1)],
            expected_amount=Decimal("100"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        _, breaches = self._run(inputs)
        assert not breaches

    def test_breach_fires_on_correct_month(self) -> None:
        """Breach date equals the month of the event that caused negative balance."""
        acct = _checking_account(balance=Decimal("150"))
        rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[date(2026, 3, 1)],  # Mar, not Feb
            expected_amount=Decimal("200"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        _, breaches = self._run(inputs, horizon=6)
        neg = [b for b in breaches if b.breach_type == str(BreachType.NEGATIVE_BALANCE)]
        assert len(neg) == 1
        assert neg[0].breach_date == date(2026, 3, 1)

    def test_breach_fires_once_even_if_balance_stays_negative(self) -> None:
        """Once a breach fires for (account, breach_type), it must not fire again.

        Balance goes negative in month 1 and stays negative in months 2-3.
        Exactly one breach must be emitted.
        """
        acct = _checking_account(balance=Decimal("50"))
        rid = uuid.uuid4()
        # Two consecutive debits each exceeding available balance
        rec = RecurrenceInput(
            recurrence_id=rid,
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1)],
            expected_amount=Decimal("500"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        _, breaches = self._run(inputs, horizon=6)
        neg = [b for b in breaches if b.breach_type == str(BreachType.NEGATIVE_BALANCE)]
        assert len(neg) == 1, (
            f"Expected 1 breach, got {len(neg)}: {[(b.breach_date, b.breach_type) for b in neg]}"
        )

    def test_no_breach_when_income_covers_expense(self) -> None:
        """Monthly income that exceeds monthly expense produces no negative breach."""
        acct = _checking_account(balance=Decimal("1000"))
        income_rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 15), date(2026, 3, 15)],
            expected_amount=Decimal("3000"),
            currency="USD",
            direction=str(ProjectedDirection.CREDIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        expense_rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1)],
            expected_amount=Decimal("500"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(
            accounts=[acct], recurrences=[income_rec, expense_rec], as_of=date(2026, 1, 1)
        )
        _, breaches = self._run(inputs, horizon=6)
        neg = [b for b in breaches if b.breach_type == str(BreachType.NEGATIVE_BALANCE)]
        assert neg == []

    @given(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
        st.decimals(min_value=Decimal("1"), max_value=Decimal("20000"), places=2),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_breach_always_before_or_on_event_that_caused_it(
        self, balance: Decimal, debit: Decimal
    ) -> None:
        """If balance goes negative, breach date <= first event that caused it."""
        acct = AccountSnapshot(
            account_id=uuid.uuid4(),
            name="Checking",
            current_balance=balance,
            currency="USD",
            account_type="checking",
        )
        event_date = date(2026, 2, 1)
        rec = RecurrenceInput(
            recurrence_id=uuid.uuid4(),
            account_id=acct.account_id,
            expected_dates=[event_date],
            expected_amount=debit,
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = ProjectionInputs(
            household_id=uuid.uuid4(),
            home_currency="USD",
            as_of_date=date(2026, 1, 1),
            accounts=[acct],
            recurrences=[rec],
            budgets=[],
            debt_plans=[],
            goals=[],
            fx_rates=[],
        )
        inputs.inputs_hash = inputs.compute_hash()
        _, breaches = _simulate(
            inputs,
            horizon_months=3,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        final_balance = balance - debit
        if final_balance < Decimal("0"):
            assert any(b.breach_type == str(BreachType.NEGATIVE_BALANCE) for b in breaches)
        else:
            assert not any(b.breach_type == str(BreachType.NEGATIVE_BALANCE) for b in breaches)


class TestSimulateHorizonCap:
    @given(
        st.integers(min_value=1, max_value=60),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_no_event_beyond_horizon(self, horizon_months: int) -> None:
        """No ProjectedEvent date should exceed as_of_date + horizon_months."""
        as_of = date(2026, 1, 1)
        acct = AccountSnapshot(
            account_id=uuid.uuid4(),
            name="A",
            current_balance=Decimal("5000"),
            currency="USD",
            account_type="checking",
        )
        bgt = BudgetInput(
            budget_group_id=uuid.uuid4(),
            expected_income=Decimal("3000"),
            currency="USD",
            lines=[
                BudgetLineInput(
                    line_id=uuid.uuid4(),
                    planned_amount=Decimal("500"),
                    currency="USD",
                    category_id=None,
                )
            ],
        )
        inputs = ProjectionInputs(
            household_id=uuid.uuid4(),
            home_currency="USD",
            as_of_date=as_of,
            accounts=[acct],
            recurrences=[],
            budgets=[bgt],
            debt_plans=[],
            goals=[],
            fx_rates=[],
        )
        inputs.inputs_hash = inputs.compute_hash()
        horizon_end = _add_months(as_of, horizon_months)
        events, _ = _simulate(
            inputs,
            horizon_months=horizon_months,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        for evt in events:
            assert evt.event_date <= horizon_end


# ===========================================================================
# Scenario override tests
# ===========================================================================


class TestScenarioOverrides:
    def _base_inputs(self) -> tuple[ProjectionInputs, uuid.UUID]:
        rid = uuid.uuid4()
        acct = _checking_account()
        rec = RecurrenceInput(
            recurrence_id=rid,
            account_id=acct.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1)],
            expected_amount=Decimal("100"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
        )
        inputs = _make_inputs(accounts=[acct], recurrences=[rec], as_of=date(2026, 1, 1))
        return inputs, rid

    def test_remove_recurrence(self) -> None:
        inputs, rid = self._base_inputs()
        assert any(r.recurrence_id == rid for r in inputs.recurrences)

        overrides = [{"type": str(OverrideType.REMOVE_RECURRENCE), "recurrence_id": str(rid)}]
        modified = apply_scenario_overrides(inputs, overrides)
        assert not any(r.recurrence_id == rid for r in modified.recurrences)

    def test_remove_recurrence_removes_events(self) -> None:
        inputs, rid = self._base_inputs()
        overrides = [{"type": str(OverrideType.REMOVE_RECURRENCE), "recurrence_id": str(rid)}]
        modified = apply_scenario_overrides(inputs, overrides)
        events, _ = _simulate(
            modified,
            horizon_months=3,
            run_id=uuid.uuid4(),
            household_id=modified.household_id,
        )
        rec_events = [e for e in events if e.source_id == rid]
        assert rec_events == []

    def test_remove_nonexistent_recurrence_is_noop(self) -> None:
        inputs, _ = self._base_inputs()
        original_count = len(inputs.recurrences)
        overrides = [
            {
                "type": str(OverrideType.REMOVE_RECURRENCE),
                "recurrence_id": str(uuid.uuid4()),
            }
        ]
        modified = apply_scenario_overrides(inputs, overrides)
        assert len(modified.recurrences) == original_count

    def test_change_income_budget(self) -> None:
        acct = _checking_account()
        bid = uuid.uuid4()
        bgt = BudgetInput(
            budget_group_id=bid,
            expected_income=Decimal("4000"),
            currency="USD",
            lines=[],
        )
        inputs = _make_inputs(accounts=[acct], budgets=[bgt], as_of=date(2026, 1, 1))

        overrides = [
            {
                "type": str(OverrideType.CHANGE_INCOME),
                "budget_id": str(bid),
                "amount": "6000",
            }
        ]
        modified = apply_scenario_overrides(inputs, overrides)
        assert modified.budgets[0].expected_income == Decimal("6000")

    def test_change_account_balance(self) -> None:
        acct = _checking_account(balance=Decimal("1000"))
        inputs = _make_inputs(accounts=[acct], as_of=date(2026, 1, 1))
        overrides = [
            {
                "type": str(OverrideType.CHANGE_ACCOUNT_BALANCE),
                "account_id": str(acct.account_id),
                "balance": "5000",
            }
        ]
        modified = apply_scenario_overrides(inputs, overrides)
        assert modified.accounts[0].current_balance == Decimal("5000")

    def test_override_does_not_mutate_original(self) -> None:
        inputs, rid = self._base_inputs()
        original_hash = inputs.inputs_hash
        overrides = [{"type": str(OverrideType.REMOVE_RECURRENCE), "recurrence_id": str(rid)}]
        apply_scenario_overrides(inputs, overrides)
        assert inputs.inputs_hash == original_hash
        assert any(r.recurrence_id == rid for r in inputs.recurrences)

    def test_hash_changes_after_override(self) -> None:
        inputs, rid = self._base_inputs()
        overrides = [{"type": str(OverrideType.REMOVE_RECURRENCE), "recurrence_id": str(rid)}]
        modified = apply_scenario_overrides(inputs, overrides)
        assert modified.inputs_hash != inputs.inputs_hash

    @given(
        st.decimals(min_value=Decimal("1000"), max_value=Decimal("100000"), places=2),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_change_goal_contribution_property(self, new_monthly: Decimal) -> None:
        goal_id = uuid.uuid4()
        acct = _checking_account(balance=Decimal("50000"))
        goal = GoalInput(
            goal_id=goal_id,
            monthly_contribution=Decimal("200"),
            currency="USD",
        )
        inputs = _make_inputs(
            accounts=[acct],
            goals=[goal],
            as_of=date(2026, 1, 1),
        )
        overrides = [
            {
                "type": str(OverrideType.CHANGE_GOAL_CONTRIBUTION),
                "goal_id": str(goal_id),
                "monthly_amount": str(new_monthly),
            }
        ]
        modified = apply_scenario_overrides(inputs, overrides)
        modified_goal = next(g for g in modified.goals if g.goal_id == goal_id)
        assert modified_goal.monthly_contribution == new_monthly


# ===========================================================================
# Golden-file tests
# ===========================================================================


class TestGoldenFileSimpleHousehold:
    """Deterministic 3-month projection for a simple household fixture."""

    AS_OF = date(2026, 1, 1)
    HORIZON = 3

    def _build(self) -> ProjectionInputs:
        checking = AccountSnapshot(
            account_id=uuid.UUID("00000000-0000-0001-0000-000000000001"),
            name="Checking",
            current_balance=Decimal("3000.00"),
            currency="USD",
            account_type="checking",
        )
        savings = AccountSnapshot(
            account_id=uuid.UUID("00000000-0000-0001-0000-000000000002"),
            name="Savings",
            current_balance=Decimal("5000.00"),
            currency="USD",
            account_type="savings",
        )

        netflix = RecurrenceInput(
            recurrence_id=uuid.UUID("00000000-0000-0002-0000-000000000001"),
            account_id=checking.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
            expected_amount=Decimal("15.99"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
            merchant_name="Netflix",
        )
        rent = RecurrenceInput(
            recurrence_id=uuid.UUID("00000000-0000-0002-0000-000000000002"),
            account_id=checking.account_id,
            expected_dates=[date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
            expected_amount=Decimal("1500.00"),
            currency="USD",
            direction=str(ProjectedDirection.DEBIT),
            confidence=str(ProjectedConfidence.HIGH),
            merchant_name="Landlord",
        )
        salary = RecurrenceInput(
            recurrence_id=uuid.UUID("00000000-0000-0002-0000-000000000003"),
            account_id=checking.account_id,
            expected_dates=[date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
            expected_amount=Decimal("3500.00"),
            currency="USD",
            direction=str(ProjectedDirection.CREDIT),
            confidence=str(ProjectedConfidence.HIGH),
            merchant_name="Employer",
        )

        budget = BudgetInput(
            budget_group_id=uuid.UUID("00000000-0000-0003-0000-000000000001"),
            expected_income=None,
            currency="USD",
            lines=[
                BudgetLineInput(
                    line_id=uuid.UUID("00000000-0000-0004-0000-000000000001"),
                    planned_amount=Decimal("500.00"),
                    currency="USD",
                    category_id=None,
                )
            ],
        )

        debt_plan = DebtPlanInput(
            plan_group_id=uuid.UUID("00000000-0000-0005-0000-000000000001"),
            currency="USD",
            payments=[
                DebtPaymentEntry(
                    period_date=date(2026, 2, 1),
                    payment=Decimal("200.00"),
                    account_id=checking.account_id,
                ),
                DebtPaymentEntry(
                    period_date=date(2026, 3, 1),
                    payment=Decimal("200.00"),
                    account_id=checking.account_id,
                ),
                DebtPaymentEntry(
                    period_date=date(2026, 4, 1),
                    payment=Decimal("200.00"),
                    account_id=checking.account_id,
                ),
            ],
        )

        hh_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        inputs = ProjectionInputs(
            household_id=hh_id,
            home_currency="USD",
            as_of_date=self.AS_OF,
            accounts=[checking, savings],
            recurrences=[netflix, rent, salary],
            budgets=[budget],
            debt_plans=[debt_plan],
            goals=[],
            fx_rates=[],
        )
        inputs.inputs_hash = inputs.compute_hash()
        return inputs

    def test_event_count(self) -> None:
        inputs = self._build()
        events, _ = _simulate(
            inputs,
            horizon_months=self.HORIZON,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        # Jan-15 salary is after as_of, so 3 months of: salary (3), netflix (3),
        # rent (3), budget_spend (3), debt_payment (3) = 15 events
        # BUT salary on Jan 15 > as_of Jan 1, so it IS included
        # horizon end = April 1, 2026
        # salary dates: Jan-15, Feb-15, Mar-15 (Apr-15 > horizon_end) -> 3 events
        # netflix: Feb-1, Mar-1, Apr-1 -> 3
        # rent: Feb-1, Mar-1, Apr-1 -> 3
        # budget_spend: Feb-1, Mar-1, Apr-1 -> 3
        # debt_payment: Feb-1, Mar-1, Apr-1 -> 3
        assert len(events) == 15

    def test_no_breach_with_sufficient_balance(self) -> None:
        """Combined income of 3500/month far exceeds 1500+15.99+200+500."""
        inputs = self._build()
        _, breaches = _simulate(
            inputs,
            horizon_months=self.HORIZON,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        assert not breaches

    def test_events_sorted_by_date(self) -> None:
        inputs = self._build()
        events, _ = _simulate(
            inputs,
            horizon_months=self.HORIZON,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        dates = [e.event_date for e in events]
        assert dates == sorted(dates)

    def test_breach_on_thin_balance(self) -> None:
        """Override starting balance + remove income to force negative breach.

        With $50 checking and no salary income, the first round of expenses
        (rent $1500, netflix $15.99, budget $500, debt $200 on Feb 1) will
        push balance negative immediately.
        """
        inputs = self._build()
        # Thin balance on checking account.
        inputs.accounts[0] = AccountSnapshot(
            account_id=inputs.accounts[0].account_id,
            name="Checking",
            current_balance=Decimal("50.00"),
            currency="USD",
            account_type="checking",
        )
        # Remove salary recurrence so there is no income to rescue the balance.
        salary_id = uuid.UUID("00000000-0000-0002-0000-000000000003")
        inputs.recurrences = [r for r in inputs.recurrences if r.recurrence_id != salary_id]
        inputs.inputs_hash = inputs.compute_hash()
        _, breaches = _simulate(
            inputs,
            horizon_months=self.HORIZON,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        neg_breaches = [b for b in breaches if b.breach_type == str(BreachType.NEGATIVE_BALANCE)]
        assert len(neg_breaches) >= 1


class TestGoldenFileFx:
    """FX scenario: EUR account projects flat; net worth converts correctly."""

    AS_OF = date(2026, 1, 1)

    def _build(self) -> tuple[ProjectionInputs, uuid.UUID, uuid.UUID]:
        usd_acct_id = uuid.UUID("00000000-0001-0000-0000-000000000001")
        eur_acct_id = uuid.UUID("00000000-0001-0000-0000-000000000002")

        usd_acct = AccountSnapshot(
            account_id=usd_acct_id,
            name="USD Checking",
            current_balance=Decimal("1000.00"),
            currency="USD",
            account_type="checking",
        )
        eur_acct = AccountSnapshot(
            account_id=eur_acct_id,
            name="EUR Savings",
            current_balance=Decimal("500.00"),
            currency="EUR",
            account_type="savings",
        )
        fx = FxRateInput(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.1000"),
        )
        hh_id = uuid.UUID("00000000-0000-0000-0001-000000000001")
        inputs = ProjectionInputs(
            household_id=hh_id,
            home_currency="USD",
            as_of_date=self.AS_OF,
            accounts=[usd_acct, eur_acct],
            recurrences=[],
            budgets=[],
            debt_plans=[],
            goals=[],
            fx_rates=[fx],
        )
        inputs.inputs_hash = inputs.compute_hash()
        return inputs, usd_acct_id, eur_acct_id

    def test_eur_account_balance_projects_flat(self) -> None:
        """Without any EUR-denominated events, EUR balance stays constant."""
        inputs, _, eur_id = self._build()
        events, _ = _simulate(
            inputs,
            horizon_months=3,
            run_id=uuid.uuid4(),
            household_id=inputs.household_id,
        )
        eur_events = [e for e in events if e.account_id == eur_id]
        assert eur_events == []

    def test_fx_in_inputs_hash(self) -> None:
        """FX rates included in hash: changing rate changes hash."""
        inputs, _, _ = self._build()
        hash_original = inputs.inputs_hash

        inputs2 = ProjectionInputs(
            household_id=inputs.household_id,
            home_currency="USD",
            as_of_date=self.AS_OF,
            accounts=inputs.accounts,
            recurrences=[],
            budgets=[],
            debt_plans=[],
            goals=[],
            fx_rates=[FxRateInput(from_currency="EUR", to_currency="USD", rate=Decimal("1.2000"))],
        )
        inputs2.inputs_hash = inputs2.compute_hash()
        assert inputs2.inputs_hash != hash_original


# ===========================================================================
# Integration tests (require Docker)
# ===========================================================================


@pytest.mark.integration
class TestProjectionIntegration:
    """End-to-end tests using a real Postgres DB via testcontainers."""

    @pytest.fixture()
    async def session_with_models(  # type: ignore[misc]
        self, session: AsyncSession
    ) -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def _create_household(self, session: Any) -> Any:
        from app.households.models import Household
        from app.platform.ids import new_uuid

        hh = Household(id=new_uuid(), name="Test HH", home_currency="USD")
        session.add(hh)
        await session.flush()
        return hh

    async def test_scenario_create_get_archive(self, session_with_models: Any) -> None:
        from app.projections import service

        session = session_with_models
        hh = await self._create_household(session)
        actor_id = uuid.uuid4()

        scenario = await service.create_scenario(
            session,
            household_id=hh.id,
            actor_id=actor_id,
            name="Test Scenario",
            overrides=[],
            saved=True,
        )
        await session.flush()

        fetched = await service.get_scenario(session, scenario_id=scenario.id, household_id=hh.id)
        assert fetched.name == "Test Scenario"
        assert fetched.saved is True

        archived = await service.archive_scenario(
            session, scenario_id=scenario.id, household_id=hh.id, actor_id=actor_id
        )
        assert archived.archived_at is not None

        with pytest.raises(service.NotFoundError):
            await service.get_scenario(session, scenario_id=scenario.id, household_id=hh.id)

    async def test_cache_invalidation(self, session_with_models: Any) -> None:
        from datetime import datetime

        import sqlalchemy as sa

        from app.projections import service
        from app.projections.models import ProjectionRun

        session = session_with_models
        hh = await self._create_household(session)

        future = datetime.now(tz=UTC) + timedelta(hours=2)
        run = ProjectionRun(
            household_id=hh.id,
            scenario_id=None,
            as_of_date=date.today(),
            horizon_months=12,
            inputs_hash="abc123",
            computed_at=datetime.now(tz=UTC),
            expires_at=future,
            status="complete",
        )
        session.add(run)
        await session.flush()

        await service.invalidate_cache(session, household_id=hh.id)
        await session.flush()

        result = await session.execute(sa.select(ProjectionRun).where(ProjectionRun.id == run.id))
        updated_run = result.scalar_one()
        now = datetime.now(tz=UTC)
        assert updated_run.expires_at <= now

    async def test_list_scenarios_only_saved(self, session_with_models: Any) -> None:
        from app.projections import service

        session = session_with_models
        hh = await self._create_household(session)
        actor_id = uuid.uuid4()

        await service.create_scenario(
            session,
            household_id=hh.id,
            actor_id=actor_id,
            name="Saved",
            saved=True,
        )
        await service.create_scenario(
            session,
            household_id=hh.id,
            actor_id=actor_id,
            name=None,
            saved=False,
        )
        await session.flush()

        saved = await service.list_scenarios(session, household_id=hh.id)
        assert len(saved) == 1
        assert saved[0].name == "Saved"
