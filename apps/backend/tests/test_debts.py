"""Tests for the debts module.

Unit tests (no DB) cover pure engine logic: amortization math, ordering,
snowball flow, method dispatch.
Integration tests (@pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests:
  - Amortization: interest = APR/12 * balance, principal = payment - interest,
    closing_balance never negative
  - Snowball flow: paid-off account minimum redirected to next; order preserved
  - Avalanche ordering: highest APR always receives extra payment first
  - Payoff monotonicity: more extra payment => same or earlier payoff date
  - Versioning: plan edit creates new version; schedule uses active version only
  - none method: no schedule rows written, no recommendations emitted
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.debts.enums import DebtPlanMethod
from app.debts.service import (
    AccountState,
    AccountTranche,
    BaselineSummary,
    NotFoundError,
    ValidationError,
    _compute_minimum,
    _run_minimums_baseline,
    archive_plan,
    compute_comparison,
    compute_schedule,
    create_plan,
    get_active_plan,
    get_plan,
    get_summary,
    list_plan_history,
    list_plans,
    simulate_schedule,
    update_plan,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_money_pos = st.decimals(min_value=Decimal("100"), max_value=Decimal("50000"), places=2)
_apr = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.36"), places=4)
_extra = st.decimals(min_value=Decimal("0"), max_value=Decimal("500"), places=2)


def _make_tranche(
    principal: Decimal = Decimal("5000"),
    apr: Decimal = Decimal("0.20"),
) -> AccountTranche:
    acct_id = uuid.uuid4()
    t = AccountTranche(
        balance_id=uuid.uuid4(),
        account_id=acct_id,
        principal=principal,
        apr=apr,
        currency="USD",
        minimum_payment=Decimal("0"),
    )
    t.minimum_payment = _compute_minimum(t)
    return t


def _make_account(
    principal: Decimal = Decimal("5000"), apr: Decimal = Decimal("0.20")
) -> AccountState:
    t = _make_tranche(principal, apr)
    return AccountState(account_id=t.account_id, tranches=[t], currency="USD")


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestMinimumPayment:
    def test_zero_balance_returns_zero(self) -> None:
        t = _make_tranche(principal=Decimal("0"))
        assert _compute_minimum(t) == Decimal("0")

    def test_floor_applied_for_small_balance(self) -> None:
        t = _make_tranche(principal=Decimal("100"))
        # 2% of 100 = 2.00, floor = 25.00
        assert _compute_minimum(t) == Decimal("25.00")

    def test_percentage_wins_for_large_balance(self) -> None:
        t = _make_tranche(principal=Decimal("5000"))
        # 2% of 5000 = 100 > 25
        assert _compute_minimum(t) == Decimal("100.00")

    def test_boundary_exactly_at_floor(self) -> None:
        t = _make_tranche(principal=Decimal("1250"))
        # 2% of 1250 = 25 == floor
        assert _compute_minimum(t) == Decimal("25.00")


class TestSimulateSchedule:
    def test_empty_accounts_returns_empty(self) -> None:
        rows = simulate_schedule(
            accounts=[],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("0"),
            snowball_flow=True,
            account_ids_order=[],
            start_date=date(2026, 1, 1),
        )
        assert rows == []

    def test_none_method_returns_empty(self) -> None:
        acct = _make_account()
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.NONE,
            monthly_extra_payment=Decimal("0"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        assert rows == []

    def test_single_account_reaches_zero(self) -> None:
        acct = _make_account(principal=Decimal("1000"), apr=Decimal("0.24"))
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("100"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        assert rows, "should produce rows"
        last = max(rows, key=lambda r: r.period_date)
        assert last.closing_balance == Decimal("0.00")
        assert last.is_payoff

    def test_closing_balance_never_negative(self) -> None:
        acct = _make_account(principal=Decimal("500"), apr=Decimal("0.18"))
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("50"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        for row in rows:
            assert row.closing_balance >= Decimal("0"), (
                f"Negative closing balance on {row.period_date}: {row.closing_balance}"
            )

    def test_interest_equals_apr_over_12_times_balance(self) -> None:
        """For first period: interest == APR/12 * opening_balance."""
        apr = Decimal("0.2400")
        principal = Decimal("3000.00")
        acct = _make_account(principal=principal, apr=apr)
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("0"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        first_period = min(rows, key=lambda r: r.period_date)
        expected_interest = (principal * apr / Decimal(12)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        assert first_period.interest == expected_interest

    def test_principal_equals_payment_minus_interest(self) -> None:
        acct = _make_account(principal=Decimal("2000"), apr=Decimal("0.12"))
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("50"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        for row in rows:
            if row.is_payoff:
                continue
            assert row.principal == row.payment - row.interest, (
                f"principal != payment - interest on {row.period_date}"
            )

    def test_opening_minus_principal_equals_closing(self) -> None:
        acct = _make_account(principal=Decimal("1500"), apr=Decimal("0.15"))
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("0"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        for row in rows:
            expected_closing = (row.opening_balance - row.principal).quantize(Decimal("0.01"))
            if expected_closing < Decimal("0"):
                expected_closing = Decimal("0")
            assert row.closing_balance == expected_closing, (
                f"opening - principal != closing on {row.period_date}"
            )


class TestAvalancheOrdering:
    def test_extra_payment_goes_to_highest_apr_first(self) -> None:
        low_apr = _make_account(principal=Decimal("3000"), apr=Decimal("0.10"))
        high_apr = _make_account(principal=Decimal("3000"), apr=Decimal("0.25"))
        extra = Decimal("200")

        rows = simulate_schedule(
            accounts=[low_apr, high_apr],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=extra,
            snowball_flow=False,
            account_ids_order=[low_apr.account_id, high_apr.account_id],
            start_date=date(2026, 1, 1),
        )

        first_period = min(rows, key=lambda r: r.period_date)
        first_high = next(
            r
            for r in rows
            if r.account_id == high_apr.account_id and r.period_date == first_period.period_date
        )
        first_low = next(
            r
            for r in rows
            if r.account_id == low_apr.account_id and r.period_date == first_period.period_date
        )

        # High APR account should receive extra payment -> higher payment
        assert first_high.payment > first_low.payment

    def test_avalanche_pays_less_total_interest_than_snowball(self) -> None:
        """Avalanche minimizes total interest vs snowball for different APRs."""
        low_apr_high_bal = _make_account(principal=Decimal("5000"), apr=Decimal("0.05"))
        high_apr_low_bal = _make_account(principal=Decimal("1000"), apr=Decimal("0.29"))
        extra = Decimal("100")
        order = [low_apr_high_bal.account_id, high_apr_low_bal.account_id]

        avalanche_rows = simulate_schedule(
            accounts=[low_apr_high_bal, high_apr_low_bal],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=extra,
            snowball_flow=True,
            account_ids_order=order,
            start_date=date(2026, 1, 1),
        )
        snowball_rows = simulate_schedule(
            accounts=[
                _make_account(principal=Decimal("5000"), apr=Decimal("0.05")),
                _make_account(principal=Decimal("1000"), apr=Decimal("0.29")),
            ],
            method=DebtPlanMethod.SNOWBALL,
            monthly_extra_payment=extra,
            snowball_flow=True,
            account_ids_order=order,
            start_date=date(2026, 1, 1),
        )

        avalanche_interest = sum(r.interest for r in avalanche_rows)
        snowball_interest = sum(r.interest for r in snowball_rows)
        assert avalanche_interest <= snowball_interest


class TestSnowballFlow:
    def test_paid_off_minimum_redirected_to_next_account(self) -> None:
        """After small account paid off, extra increases for large account."""
        small_f = _make_account(principal=Decimal("300"), apr=Decimal("0.12"))
        large_f = _make_account(principal=Decimal("2000"), apr=Decimal("0.12"))
        small_nf = _make_account(principal=Decimal("300"), apr=Decimal("0.12"))
        large_nf = _make_account(principal=Decimal("2000"), apr=Decimal("0.12"))

        rows_flow = simulate_schedule(
            accounts=[small_f, large_f],
            method=DebtPlanMethod.SNOWBALL,
            monthly_extra_payment=Decimal("150"),
            snowball_flow=True,
            account_ids_order=[small_f.account_id, large_f.account_id],
            start_date=date(2026, 1, 1),
        )
        rows_no_flow = simulate_schedule(
            accounts=[small_nf, large_nf],
            method=DebtPlanMethod.SNOWBALL,
            monthly_extra_payment=Decimal("150"),
            snowball_flow=False,
            account_ids_order=[small_nf.account_id, large_nf.account_id],
            start_date=date(2026, 1, 1),
        )

        # Snowball flow should pay off large account sooner (or same)
        large_payoff_flow = max(
            (
                r.period_date
                for r in rows_flow
                if r.account_id == large_f.account_id and r.is_payoff
            ),
            default=None,
        )
        large_payoff_no_flow = max(
            (
                r.period_date
                for r in rows_no_flow
                if r.account_id == large_nf.account_id and r.is_payoff
            ),
            default=None,
        )
        assert large_payoff_flow is not None
        assert large_payoff_no_flow is not None
        assert large_payoff_flow <= large_payoff_no_flow

    def test_snowball_sorts_by_balance_ascending(self) -> None:
        """Snowball prioritizes smallest balance first."""
        large = _make_account(principal=Decimal("4000"), apr=Decimal("0.15"))
        small = _make_account(principal=Decimal("800"), apr=Decimal("0.15"))
        order = [large.account_id, small.account_id]

        rows = simulate_schedule(
            accounts=[large, small],
            method=DebtPlanMethod.SNOWBALL,
            monthly_extra_payment=Decimal("200"),
            snowball_flow=False,
            account_ids_order=order,
            start_date=date(2026, 1, 1),
        )

        first_period = min(rows, key=lambda r: r.period_date)
        small_first = next(
            r
            for r in rows
            if r.account_id == small.account_id and r.period_date == first_period.period_date
        )
        large_first = next(
            r
            for r in rows
            if r.account_id == large.account_id and r.period_date == first_period.period_date
        )

        # Small account (priority) gets extra payment -> higher payment
        assert small_first.payment >= large_first.payment


class TestPayoffMonotonicity:
    """More extra payment => same or earlier payoff date."""

    def test_more_extra_earlier_payoff(self) -> None:
        acct_low = _make_account(principal=Decimal("3000"), apr=Decimal("0.18"))
        acct_high = _make_account(principal=Decimal("3000"), apr=Decimal("0.18"))

        rows_low = simulate_schedule(
            accounts=[acct_low],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("50"),
            snowball_flow=True,
            account_ids_order=[acct_low.account_id],
            start_date=date(2026, 1, 1),
        )
        rows_high = simulate_schedule(
            accounts=[acct_high],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("200"),
            snowball_flow=True,
            account_ids_order=[acct_high.account_id],
            start_date=date(2026, 1, 1),
        )

        payoff_low = max((r.period_date for r in rows_low if r.is_payoff), default=None)
        payoff_high = max((r.period_date for r in rows_high if r.is_payoff), default=None)

        assert payoff_low is not None
        assert payoff_high is not None
        assert payoff_high <= payoff_low


class TestNoneMethod:
    def test_returns_empty_rows(self) -> None:
        acct = _make_account()
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.NONE,
            monthly_extra_payment=Decimal("100"),
            snowball_flow=True,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        assert rows == []


class TestBaselineComparison:
    def test_baseline_no_extra_payment(self) -> None:
        acct = _make_account(principal=Decimal("2000"), apr=Decimal("0.18"))
        baseline = _run_minimums_baseline([acct], [acct.account_id], "USD")
        assert baseline.total_interest > Decimal("0")
        assert isinstance(baseline, BaselineSummary)

    def test_extra_payment_reduces_interest_vs_baseline(self) -> None:
        acct_ref = _make_account(principal=Decimal("5000"), apr=Decimal("0.22"))
        baseline = _run_minimums_baseline([acct_ref], [acct_ref.account_id], "USD")

        acct_extra = _make_account(principal=Decimal("5000"), apr=Decimal("0.22"))
        rows_extra = simulate_schedule(
            accounts=[acct_extra],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("200"),
            snowball_flow=True,
            account_ids_order=[acct_extra.account_id],
            start_date=date.today().replace(day=1),
        )
        extra_interest = sum(r.interest for r in rows_extra)
        assert extra_interest < baseline.total_interest


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


@given(
    principal=_money_pos,
    apr=_apr,
    extra=_extra,
)
@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_closing_balance_never_negative(
    principal: Decimal,
    apr: Decimal,
    extra: Decimal,
) -> None:
    acct = _make_account(principal=principal, apr=apr)
    rows = simulate_schedule(
        accounts=[acct],
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=extra,
        snowball_flow=True,
        account_ids_order=[acct.account_id],
        start_date=date(2026, 1, 1),
    )
    for row in rows:
        assert row.closing_balance >= Decimal("0"), (
            f"Negative closing_balance {row.closing_balance} on {row.period_date} "
            f"(principal={principal}, apr={apr}, extra={extra})"
        )


@given(
    principal=_money_pos,
    apr=_apr,
)
@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_interest_formula(principal: Decimal, apr: Decimal) -> None:
    """First period interest exactly equals APR/12 * balance."""
    acct = _make_account(principal=principal, apr=apr)
    rows = simulate_schedule(
        accounts=[acct],
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=Decimal("0"),
        snowball_flow=True,
        account_ids_order=[acct.account_id],
        start_date=date(2026, 1, 1),
    )
    if not rows:
        return
    first = min(rows, key=lambda r: r.period_date)
    expected = (principal * apr / Decimal(12)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert first.interest == expected


@given(
    extra_low=st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), places=2),
    extra_high=st.decimals(min_value=Decimal("150"), max_value=Decimal("500"), places=2),
    principal=_money_pos,
    apr=_apr,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_payoff_monotonicity(
    extra_low: Decimal,
    extra_high: Decimal,
    principal: Decimal,
    apr: Decimal,
) -> None:
    """Higher extra payment never results in later payoff date."""
    acct_low = _make_account(principal=principal, apr=apr)
    acct_high = _make_account(principal=principal, apr=apr)

    rows_low = simulate_schedule(
        accounts=[acct_low],
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=extra_low,
        snowball_flow=True,
        account_ids_order=[acct_low.account_id],
        start_date=date(2026, 1, 1),
    )
    rows_high = simulate_schedule(
        accounts=[acct_high],
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=extra_high,
        snowball_flow=True,
        account_ids_order=[acct_high.account_id],
        start_date=date(2026, 1, 1),
    )

    payoff_low = max((r.period_date for r in rows_low if r.is_payoff), default=None)
    payoff_high = max((r.period_date for r in rows_high if r.is_payoff), default=None)

    if payoff_low is None or payoff_high is None:
        return
    assert payoff_high <= payoff_low, (
        f"Higher extra ({extra_high}) yields later payoff ({payoff_high}) "
        f"than lower extra ({extra_low} -> {payoff_low})"
    )


@given(
    principal_a=_money_pos,
    apr_a=_apr,
    principal_b=_money_pos,
    apr_b=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.35"), places=4),
    extra=_extra,
)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_snowball_flow_earlier_or_equal_payoff(
    principal_a: Decimal,
    apr_a: Decimal,
    principal_b: Decimal,
    apr_b: Decimal,
    extra: Decimal,
) -> None:
    """Snowball flow (redirect minimums) never delays payoff vs no-flow."""
    small_bal = min(principal_a, principal_b)
    large_bal = max(principal_a, principal_b)
    small_apr = apr_a
    large_apr = apr_b

    def _make_pair() -> tuple[AccountState, AccountState]:
        small = _make_account(principal=small_bal, apr=small_apr)
        large = _make_account(principal=large_bal, apr=large_apr)
        return small, large

    small_f, large_f = _make_pair()
    small_nf, large_nf = _make_pair()

    rows_flow = simulate_schedule(
        accounts=[small_f, large_f],
        method=DebtPlanMethod.SNOWBALL,
        monthly_extra_payment=extra,
        snowball_flow=True,
        account_ids_order=[small_f.account_id, large_f.account_id],
        start_date=date(2026, 1, 1),
    )
    rows_no_flow = simulate_schedule(
        accounts=[small_nf, large_nf],
        method=DebtPlanMethod.SNOWBALL,
        monthly_extra_payment=extra,
        snowball_flow=False,
        account_ids_order=[small_nf.account_id, large_nf.account_id],
        start_date=date(2026, 1, 1),
    )

    all_ids = {small_f.account_id, large_f.account_id}
    flow_paid = {r.account_id for r in rows_flow if r.is_payoff}
    nf_paid = {r.account_id for r in rows_no_flow if r.is_payoff}

    # Only compare when no-flow scenario fully completes; if it leaves debts
    # unpaid, flow (which redirects freed minimums) can only be equal or better.
    if not nf_paid >= all_ids:
        return

    assert flow_paid >= all_ids, "flow leaves accounts unpaid but no-flow completes them"

    payoff_flow = max(r.period_date for r in rows_flow if r.is_payoff)
    payoff_no_flow = max(r.period_date for r in rows_no_flow if r.is_payoff)
    assert payoff_flow <= payoff_no_flow


# ===========================================================================
# Multi-tranche unit tests
# ===========================================================================


def _make_multi_tranche(specs: list[tuple[Decimal, Decimal]]) -> AccountState:
    """Build one AccountState with multiple tranches from (principal, apr) pairs."""
    acct_id = uuid.uuid4()
    tranches = []
    for principal, apr in specs:
        t = AccountTranche(
            balance_id=uuid.uuid4(),
            account_id=acct_id,
            principal=principal,
            apr=apr,
            currency="USD",
            minimum_payment=Decimal("0"),
        )
        t.minimum_payment = _compute_minimum(t)
        tranches.append(t)
    return AccountState(account_id=acct_id, tranches=tranches, currency="USD")


class TestMultiTranche:
    def test_intra_account_highest_apr_paid_first(self) -> None:
        """Extra payment within one account must target the highest-APR tranche first.

        Low-APR tranche is listed first to expose any list-order bug.
        Correct: total interest equals a two-account avalanche run with same APRs.
        """
        low_apr = Decimal("0.10")
        high_apr = Decimal("0.30")
        low_bal = Decimal("5000")
        high_bal = Decimal("500")
        extra = Decimal("300")

        # Multi-tranche: low-APR listed first
        multi = _make_multi_tranche([(low_bal, low_apr), (high_bal, high_apr)])

        # Reference: two separate accounts in avalanche order (high-APR gets extra)
        high_ref = _make_account(principal=high_bal, apr=high_apr)
        low_ref = _make_account(principal=low_bal, apr=low_apr)

        multi_rows = simulate_schedule(
            accounts=[multi],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=extra,
            snowball_flow=False,
            account_ids_order=[multi.account_id],
            start_date=date(2026, 1, 1),
        )
        ref_rows = simulate_schedule(
            accounts=[high_ref, low_ref],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=extra,
            snowball_flow=False,
            account_ids_order=[high_ref.account_id, low_ref.account_id],
            start_date=date(2026, 1, 1),
        )

        multi_interest = sum(r.interest for r in multi_rows)
        ref_interest = sum(r.interest for r in ref_rows)
        assert multi_interest == ref_interest, (
            f"Multi-tranche total interest {multi_interest} != reference {ref_interest}; "
            "extra payment applied to wrong tranche"
        )

    def test_five_tranches_zero_apr_accrues_no_interest(self) -> None:
        """Zero-APR promotional tranches must never accrue interest."""
        specs: list[tuple[Decimal, Decimal]] = [
            (Decimal("2000"), Decimal("0.00")),
            (Decimal("3000"), Decimal("0.00")),
            (Decimal("1500"), Decimal("0.18")),
            (Decimal("1000"), Decimal("0.00")),
            (Decimal("500"), Decimal("0.24")),
        ]
        acct = _make_multi_tranche(specs)
        # Assign zero-APR balance IDs so we can check interest per tranche;
        # since rows are per-account, verify globally: interest only from non-zero tranches.
        zero_apr_total = sum(p for p, a in specs if a == Decimal("0.00"))
        nonzero_apr_balances = [(p, a) for p, a in specs if a > Decimal("0.00")]

        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("200"),
            snowball_flow=False,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )

        # First period interest must equal sum of (nonzero_apr * balance / 12)
        first_period = min(rows, key=lambda r: r.period_date)
        expected = sum(
            (p * a / Decimal(12)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            for p, a in nonzero_apr_balances
        )
        assert first_period.interest == expected, (
            f"Zero-APR tranches accrued interest: got {first_period.interest}, expected {expected}"
        )
        assert zero_apr_total > Decimal("0")

    def test_closing_balance_never_negative_multi_tranche(self) -> None:
        """Closing balance stays >= 0 for multi-tranche accounts."""
        acct = _make_multi_tranche(
            [
                (Decimal("800"), Decimal("0.20")),
                (Decimal("300"), Decimal("0.15")),
                (Decimal("150"), Decimal("0.30")),
            ]
        )
        rows = simulate_schedule(
            accounts=[acct],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=Decimal("100"),
            snowball_flow=False,
            account_ids_order=[acct.account_id],
            start_date=date(2026, 1, 1),
        )
        for row in rows:
            assert row.closing_balance >= Decimal("0"), (
                f"Negative closing balance {row.closing_balance} on {row.period_date}"
            )

    def test_payoff_overshoot_cascades_to_next_account(self) -> None:
        """When priority account pays off, excess redirects to next account same period.

        Account A: $200 at 20% APR (high APR = priority)
        Account B: $3000 at 10% APR
        Extra: $500 (far exceeds A's payoff amount)

        After period 1 Account B must receive the excess beyond A's payoff.
        """
        acct_a = _make_account(principal=Decimal("200"), apr=Decimal("0.20"))
        acct_b = _make_account(principal=Decimal("3000"), apr=Decimal("0.10"))
        extra = Decimal("500")

        rows = simulate_schedule(
            accounts=[acct_a, acct_b],
            method=DebtPlanMethod.AVALANCHE,
            monthly_extra_payment=extra,
            snowball_flow=False,
            account_ids_order=[acct_a.account_id, acct_b.account_id],
            start_date=date(2026, 1, 1),
        )

        first_period = min(rows, key=lambda r: r.period_date)

        row_a = next(
            r
            for r in rows
            if r.account_id == acct_a.account_id and r.period_date == first_period.period_date
        )
        row_b = next(
            r
            for r in rows
            if r.account_id == acct_b.account_id and r.period_date == first_period.period_date
        )

        # A must be paid off in period 1
        assert row_a.is_payoff, "Account A should pay off in period 1"

        # A's payoff amount = ~$203.33; extra was $500; excess ≈ $296.67
        # B's minimum ≈ $60; B's payment should be minimum + excess >> minimum
        b_minimum = _compute_minimum(acct_b.tranches[0])
        assert row_b.payment > b_minimum, (
            f"Excess not cascaded: B payment {row_b.payment} <= B minimum {b_minimum}"
        )

    def test_total_minimum_equals_sum_of_tranche_minimums(self) -> None:
        """AccountState.total_minimum equals _compute_minimum() per tranche sum."""
        acct = _make_multi_tranche(
            [
                (Decimal("5000"), Decimal("0.18")),
                (Decimal("2000"), Decimal("0.24")),
                (Decimal("100"), Decimal("0.15")),
            ]
        )
        expected = sum(_compute_minimum(t) for t in acct.tranches)
        assert acct.total_minimum == expected


@given(
    specs=st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
            st.decimals(min_value=Decimal("0.00"), max_value=Decimal("0.36"), places=4),
        ),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_multi_tranche_interest_independent(
    specs: list[tuple[Decimal, Decimal]],
) -> None:
    """First-period total interest equals sum of per-tranche (APR/12 * principal)."""
    acct = _make_multi_tranche(specs)
    rows = simulate_schedule(
        accounts=[acct],
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=Decimal("0"),
        snowball_flow=False,
        account_ids_order=[acct.account_id],
        start_date=date(2026, 1, 1),
    )
    if not rows:
        return
    first = min(rows, key=lambda r: r.period_date)
    expected = sum((p * a / Decimal(12)).quantize(Decimal("0.01"), ROUND_HALF_UP) for p, a in specs)
    assert first.interest == expected, (
        f"Interest {first.interest} != expected {expected} for specs {specs}"
    )


@given(
    specs=st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=2),
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.36"), places=4),
        ),
        min_size=1,
        max_size=6,
    )
)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_total_minimum_equals_tranche_sum(
    specs: list[tuple[Decimal, Decimal]],
) -> None:
    """AccountState.total_minimum == sum(_compute_minimum(t)) for all tranches."""
    acct = _make_multi_tranche(specs)
    expected = sum(_compute_minimum(t) for t in acct.tranches)
    assert acct.total_minimum == expected


# ===========================================================================
# Integration tests (require real Postgres)
# ===========================================================================


@pytest.fixture()
async def db_session_debts(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    yield session


async def _bootstrap(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create household + user; return (household_id, user_id)."""
    from app.households.enums import VisibilityMode
    from app.households.service import create_household, create_user

    user = await create_user(
        session,
        email="debt@test.com",
        display_name="Debt Tester",
        password="test-password-123",  # pragma: allowlist secret
    )
    await session.flush()
    household = await create_household(
        session,
        name="Debt Household",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    await session.flush()
    return household.id, user.id


@pytest.mark.integration
async def test_create_and_get_plan(db_session_debts: AsyncSession) -> None:
    hh_id, user_id = await _bootstrap(db_session_debts)

    plan = await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="My Debt Plan",
        method=DebtPlanMethod.AVALANCHE,
        monthly_extra_payment=Decimal("100"),
        currency="USD",
    )
    await db_session_debts.flush()

    retrieved = await get_plan(
        db_session_debts, plan_group_id=plan.plan_group_id, household_id=hh_id
    )
    assert retrieved.id == plan.id
    assert retrieved.name == "My Debt Plan"
    assert retrieved.method == "avalanche"
    assert retrieved.monthly_extra_payment == Decimal("100")


@pytest.mark.integration
async def test_plan_versioning(db_session_debts: AsyncSession) -> None:
    """Editing a plan creates a new version; original version preserved."""
    hh_id, user_id = await _bootstrap(db_session_debts)

    plan_v1 = await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="Plan v1",
        method=DebtPlanMethod.SNOWBALL,
        effective_from=date(2026, 1, 1),
    )
    await db_session_debts.flush()
    v1_id = plan_v1.id
    group_id = plan_v1.plan_group_id

    plan_v2 = await update_plan(
        db_session_debts,
        plan_group_id=group_id,
        household_id=hh_id,
        actor_id=user_id,
        name="Plan v2",
        method=DebtPlanMethod.AVALANCHE,
        effective_from=date(2026, 3, 1),
    )
    await db_session_debts.flush()

    # Current version is v2
    current = await get_plan(db_session_debts, plan_group_id=group_id, household_id=hh_id)
    assert current.id == plan_v2.id
    assert current.name == "Plan v2"

    # v1 still exists in history
    history = await list_plan_history(db_session_debts, plan_group_id=group_id, household_id=hh_id)
    ids = [p.id for p in history]
    assert v1_id in ids
    assert plan_v2.id in ids

    # get_active_plan returns correct version for a given date
    active_jan = await get_active_plan(
        db_session_debts,
        plan_group_id=group_id,
        household_id=hh_id,
        as_of_date=date(2026, 2, 1),
    )
    assert active_jan.id == v1_id

    active_mar = await get_active_plan(
        db_session_debts,
        plan_group_id=group_id,
        household_id=hh_id,
        as_of_date=date(2026, 4, 1),
    )
    assert active_mar.id == plan_v2.id


@pytest.mark.integration
async def test_archive_plan(db_session_debts: AsyncSession) -> None:
    hh_id, user_id = await _bootstrap(db_session_debts)

    plan = await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="To Archive",
        method=DebtPlanMethod.NONE,
    )
    await db_session_debts.flush()

    await archive_plan(
        db_session_debts,
        plan_group_id=plan.plan_group_id,
        household_id=hh_id,
        actor_id=user_id,
    )
    await db_session_debts.flush()

    with pytest.raises(NotFoundError):
        await get_plan(db_session_debts, plan_group_id=plan.plan_group_id, household_id=hh_id)


@pytest.mark.integration
async def test_list_plans(db_session_debts: AsyncSession) -> None:
    hh_id, user_id = await _bootstrap(db_session_debts)

    await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="Plan A",
        method=DebtPlanMethod.AVALANCHE,
    )
    await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="Plan B",
        method=DebtPlanMethod.SNOWBALL,
    )
    await db_session_debts.flush()

    plans = await list_plans(db_session_debts, household_id=hh_id)
    assert len(plans) == 2


@pytest.mark.integration
async def test_none_method_plan_compute_returns_empty_summary(
    db_session_debts: AsyncSession,
) -> None:
    """NONE method: compute_schedule writes no rows, returns zeroed summary."""
    hh_id, user_id = await _bootstrap(db_session_debts)

    plan = await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="Tracking Only",
        method=DebtPlanMethod.NONE,
        account_ids=[],
    )
    await db_session_debts.flush()

    summary = await compute_schedule(
        db_session_debts,
        plan_group_id=plan.plan_group_id,
        household_id=hh_id,
    )
    await db_session_debts.flush()

    assert summary.months_to_payoff == 0
    assert summary.total_interest == Decimal("0")

    # No schedule rows written
    result = await db_session_debts.execute(
        sa.select(sa.func.count())
        .select_from(sa.text("debts_debt_plan_schedule"))
        .where(sa.text(f"plan_id = '{plan.id}'"))
    )
    count = result.scalar()
    assert count == 0 or count is None


@pytest.mark.integration
async def test_not_found_errors(db_session_debts: AsyncSession) -> None:
    hh_id, _ = await _bootstrap(db_session_debts)
    fake_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await get_plan(db_session_debts, plan_group_id=fake_id, household_id=hh_id)

    with pytest.raises(NotFoundError):
        await get_summary(db_session_debts, plan_group_id=fake_id, household_id=hh_id)


@pytest.mark.integration
async def test_comparison_validation_error(db_session_debts: AsyncSession) -> None:
    hh_id, user_id = await _bootstrap(db_session_debts)
    plan = await create_plan(
        db_session_debts,
        household_id=hh_id,
        actor_id=user_id,
        name="Plan",
        method=DebtPlanMethod.AVALANCHE,
    )
    await db_session_debts.flush()

    # compute_schedule needed before comparison
    await compute_schedule(
        db_session_debts,
        plan_group_id=plan.plan_group_id,
        household_id=hh_id,
    )
    await db_session_debts.flush()

    with pytest.raises(ValidationError):
        await compute_comparison(
            db_session_debts,
            plan_group_id=plan.plan_group_id,
            household_id=hh_id,
            compare="invalid_method",
        )
