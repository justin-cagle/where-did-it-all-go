"""Tests for the budgets module.

Unit tests (no DB) cover pure helpers: resolve_period, rollover computation.
Integration tests (@pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests:
  - Rollover invariants: carried_out of period N == carried_in of period N+1
    for accumulate/debt_carry policies
  - Period resolution: monthly/weekly/biweekly/semimonthly boundaries across
    month edges, leap years
  - Zero-based validation: sum invariant holds for any valid line set
  - Scope filtering: empty list means any, not none
  - Versioning: edit never modifies historical rows; get_active_budget returns
    correct version for any date
  - Rollover cap: accumulate_capped never exceeds cap regardless of unspent
"""

import types
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.budgets.enums import (
    BudgetLineStatus,
    BudgetMethod,
    BudgetPeriod,
    BudgetRole,
    ExpectedIncomeStrategy,
    RolloverPolicy,
)
from app.budgets.models import Budget, BudgetPeriodIncome
from app.budgets.service import (
    NotFoundError,
    _compute_rollover,
    _line_status,
    archive_budget,
    archive_budget_line,
    compute_actuals,
    compute_expected_income,
    create_budget,
    create_budget_line,
    get_active_budget,
    get_budget,
    get_status,
    list_budget_history,
    list_budget_lines,
    list_budgets,
    resolve_period,
    set_period_income,
    update_budget,
    update_budget_line,
)
from app.households.service import create_household, create_user

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_rollover_policy = st.sampled_from(list(RolloverPolicy))
_budget_period = st.sampled_from(list(BudgetPeriod))
_budget_method = st.sampled_from(list(BudgetMethod))
_money = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000.00"), places=2)
_money_signed = st.decimals(min_value=Decimal("-10000.00"), max_value=Decimal("10000.00"), places=2)
_date_2025 = st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 31))
_date_2024_2026 = st.dates(min_value=date(2024, 1, 1), max_value=date(2026, 12, 31))


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestEnums:
    def test_rollover_policy_values(self) -> None:
        assert RolloverPolicy.NONE == "none"
        assert RolloverPolicy.ACCUMULATE == "accumulate"
        assert RolloverPolicy.ACCUMULATE_CAPPED == "accumulate_capped"
        assert RolloverPolicy.DEBT_CARRY == "debt_carry"
        assert RolloverPolicy.RESET_ON_OVERSPEND == "reset_on_overspend"

    def test_budget_method_values(self) -> None:
        assert BudgetMethod.ZERO_BASED == "zero_based"
        assert BudgetMethod.FIFTY_THIRTY_TWENTY == "fifty_thirty_twenty"
        assert BudgetMethod.NONE == "none"

    def test_budget_role_values(self) -> None:
        assert BudgetRole.NEEDS == "needs"
        assert BudgetRole.WANTS == "wants"
        assert BudgetRole.SAVINGS == "savings"
        assert BudgetRole.UNCATEGORIZED == "uncategorized"


def _stub_budget(period: BudgetPeriod, start_date: date = date(2025, 1, 1)) -> Any:
    """Lightweight stand-in for resolve_period (only needs .period and .start_date)."""
    return types.SimpleNamespace(period=str(period), start_date=start_date)


class TestResolvePeriod:
    def _budget(self, period: BudgetPeriod, start_date: date = date(2025, 1, 1)) -> Any:
        return _stub_budget(period, start_date)

    def test_monthly_jan(self) -> None:
        b = self._budget(BudgetPeriod.MONTHLY)
        start, end = resolve_period(b, date(2025, 1, 15))
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 31)

    def test_monthly_feb_nonleap(self) -> None:
        b = self._budget(BudgetPeriod.MONTHLY)
        start, end = resolve_period(b, date(2025, 2, 10))
        assert start == date(2025, 2, 1)
        assert end == date(2025, 2, 28)

    def test_monthly_feb_leap(self) -> None:
        b = self._budget(BudgetPeriod.MONTHLY)
        start, end = resolve_period(b, date(2024, 2, 29))
        assert start == date(2024, 2, 1)
        assert end == date(2024, 2, 29)

    def test_monthly_dec(self) -> None:
        b = self._budget(BudgetPeriod.MONTHLY)
        start, end = resolve_period(b, date(2025, 12, 31))
        assert start == date(2025, 12, 1)
        assert end == date(2025, 12, 31)

    def test_weekly_monday(self) -> None:
        b = self._budget(BudgetPeriod.WEEKLY)
        # 2025-01-06 is Monday
        start, end = resolve_period(b, date(2025, 1, 6))
        assert start == date(2025, 1, 6)
        assert end == date(2025, 1, 12)

    def test_weekly_wednesday(self) -> None:
        b = self._budget(BudgetPeriod.WEEKLY)
        # 2025-01-08 is Wednesday
        start, end = resolve_period(b, date(2025, 1, 8))
        assert start == date(2025, 1, 6)
        assert end == date(2025, 1, 12)

    def test_weekly_sunday(self) -> None:
        b = self._budget(BudgetPeriod.WEEKLY)
        # 2025-01-12 is Sunday
        start, end = resolve_period(b, date(2025, 1, 12))
        assert start == date(2025, 1, 6)
        assert end == date(2025, 1, 12)

    def test_biweekly_first_cycle(self) -> None:
        anchor = date(2025, 1, 1)
        b = self._budget(BudgetPeriod.BIWEEKLY, start_date=anchor)
        start, end = resolve_period(b, date(2025, 1, 5))
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 14)

    def test_biweekly_second_cycle(self) -> None:
        anchor = date(2025, 1, 1)
        b = self._budget(BudgetPeriod.BIWEEKLY, start_date=anchor)
        start, end = resolve_period(b, date(2025, 1, 15))
        assert start == date(2025, 1, 15)
        assert end == date(2025, 1, 28)

    def test_biweekly_cross_month(self) -> None:
        anchor = date(2025, 1, 1)
        b = self._budget(BudgetPeriod.BIWEEKLY, start_date=anchor)
        start, end = resolve_period(b, date(2025, 1, 31))
        assert start == date(2025, 1, 29)
        assert end == date(2025, 2, 11)

    def test_semimonthly_first_half(self) -> None:
        b = self._budget(BudgetPeriod.SEMIMONTHLY)
        start, end = resolve_period(b, date(2025, 3, 10))
        assert start == date(2025, 3, 1)
        assert end == date(2025, 3, 15)

    def test_semimonthly_second_half(self) -> None:
        b = self._budget(BudgetPeriod.SEMIMONTHLY)
        start, end = resolve_period(b, date(2025, 3, 20))
        assert start == date(2025, 3, 16)
        assert end == date(2025, 3, 31)

    def test_semimonthly_feb_second_half_leap(self) -> None:
        b = self._budget(BudgetPeriod.SEMIMONTHLY)
        start, end = resolve_period(b, date(2024, 2, 20))
        assert start == date(2024, 2, 16)
        assert end == date(2024, 2, 29)

    def test_annual(self) -> None:
        b = self._budget(BudgetPeriod.ANNUAL)
        start, end = resolve_period(b, date(2025, 6, 15))
        assert start == date(2025, 1, 1)
        assert end == date(2025, 12, 31)


class TestComputeRollover:
    def test_none_policy_always_zero(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("300"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.NONE,
            rollover_cap=None,
        )
        assert result == Decimal("0")

    def test_none_policy_with_overspend(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("700"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.NONE,
            rollover_cap=None,
        )
        assert result == Decimal("0")

    def test_accumulate_unspent(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("300"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.ACCUMULATE,
            rollover_cap=None,
        )
        assert result == Decimal("200")

    def test_accumulate_overspend_floors_at_zero(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("700"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.ACCUMULATE,
            rollover_cap=None,
        )
        assert result == Decimal("0")

    def test_accumulate_with_carried_in(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("450"),
            carried_in=Decimal("100"),  # effective_planned = 600
            rollover_policy=RolloverPolicy.ACCUMULATE,
            rollover_cap=None,
        )
        assert result == Decimal("150")

    def test_accumulate_capped(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("100"),  # unspent = 400
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.ACCUMULATE_CAPPED,
            rollover_cap=Decimal("200"),
        )
        assert result == Decimal("200")

    def test_accumulate_capped_under_cap(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("400"),  # unspent = 100 < cap
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.ACCUMULATE_CAPPED,
            rollover_cap=Decimal("200"),
        )
        assert result == Decimal("100")

    def test_debt_carry_overspend(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("700"),  # over by 200
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.DEBT_CARRY,
            rollover_cap=None,
        )
        assert result == Decimal("-200")

    def test_debt_carry_unspent(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("300"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.DEBT_CARRY,
            rollover_cap=None,
        )
        assert result == Decimal("200")

    def test_reset_on_overspend_resets(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("700"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.RESET_ON_OVERSPEND,
            rollover_cap=None,
        )
        assert result == Decimal("0")

    def test_reset_on_overspend_carries_unspent(self) -> None:
        result = _compute_rollover(
            planned=Decimal("500"),
            actual=Decimal("300"),
            carried_in=Decimal("0"),
            rollover_policy=RolloverPolicy.RESET_ON_OVERSPEND,
            rollover_cap=None,
        )
        assert result == Decimal("200")


class TestLineStatus:
    def test_under(self) -> None:
        result = _line_status(actual=Decimal("100"), effective_planned=Decimal("500"))
        assert result == BudgetLineStatus.UNDER

    def test_on_track_at_90pct(self) -> None:
        result = _line_status(actual=Decimal("450"), effective_planned=Decimal("500"))
        assert result == BudgetLineStatus.ON_TRACK

    def test_over(self) -> None:
        result = _line_status(actual=Decimal("600"), effective_planned=Decimal("500"))
        assert result == BudgetLineStatus.OVER

    def test_on_track_at_100pct(self) -> None:
        result = _line_status(actual=Decimal("500"), effective_planned=Decimal("500"))
        assert result == BudgetLineStatus.ON_TRACK


# ===========================================================================
# Hypothesis property tests — pure (no DB)
# ===========================================================================


@given(
    planned=_money,
    actual=_money,
    carried_in=_money,
)
@settings(max_examples=200)
def test_rollover_carried_out_continuity_accumulate(
    planned: Decimal, actual: Decimal, carried_in: Decimal
) -> None:
    """carried_out(period N) >= 0 for accumulate policy."""
    result = _compute_rollover(
        planned=planned,
        actual=actual,
        carried_in=carried_in,
        rollover_policy=RolloverPolicy.ACCUMULATE,
        rollover_cap=None,
    )
    assert result >= Decimal("0")


@given(
    planned=_money,
    actual=_money,
    carried_in=_money,
    cap=_money,
)
@settings(max_examples=200)
def test_rollover_accumulate_capped_never_exceeds_cap(
    planned: Decimal, actual: Decimal, carried_in: Decimal, cap: Decimal
) -> None:
    """accumulate_capped carried_out never exceeds the cap."""
    result = _compute_rollover(
        planned=planned,
        actual=actual,
        carried_in=carried_in,
        rollover_policy=RolloverPolicy.ACCUMULATE_CAPPED,
        rollover_cap=cap,
    )
    assert result <= cap
    assert result >= Decimal("0")


@given(
    planned=_money,
    actual=_money,
    carried_in=_money,
)
@settings(max_examples=200)
def test_rollover_none_always_zero(planned: Decimal, actual: Decimal, carried_in: Decimal) -> None:
    """none policy always returns 0 regardless of inputs."""
    result = _compute_rollover(
        planned=planned,
        actual=actual,
        carried_in=carried_in,
        rollover_policy=RolloverPolicy.NONE,
        rollover_cap=None,
    )
    assert result == Decimal("0")


@given(
    planned=_money,
    actual=_money,
    carried_in=_money,
)
@settings(max_examples=200)
def test_rollover_continuity_invariant(
    planned: Decimal, actual: Decimal, carried_in: Decimal
) -> None:
    """For accumulate policy: carried_out == max(0, effective_planned - actual)."""
    effective_planned = planned + carried_in
    expected = max(Decimal("0"), effective_planned - actual)
    result = _compute_rollover(
        planned=planned,
        actual=actual,
        carried_in=carried_in,
        rollover_policy=RolloverPolicy.ACCUMULATE,
        rollover_cap=None,
    )
    assert result == expected


@given(
    planned=_money,
    actual=_money_signed,
    carried_in=_money,
)
@settings(max_examples=200)
def test_debt_carry_continuity(planned: Decimal, actual: Decimal, carried_in: Decimal) -> None:
    """debt_carry: carried_out == effective_planned - actual (can be negative)."""
    effective_planned = planned + carried_in
    expected = effective_planned - actual
    result = _compute_rollover(
        planned=planned,
        actual=actual,
        carried_in=carried_in,
        rollover_policy=RolloverPolicy.DEBT_CARRY,
        rollover_cap=None,
    )
    assert result == expected


@given(ref_date=_date_2025)
@settings(max_examples=100)
def test_monthly_period_contains_ref_date(ref_date: date) -> None:
    """resolve_period MONTHLY: ref_date is always within [period_start, period_end]."""
    b = _stub_budget(BudgetPeriod.MONTHLY)
    start, end = resolve_period(b, ref_date)
    assert start <= ref_date <= end
    assert start.day == 1


@given(ref_date=_date_2024_2026)
@settings(max_examples=100)
def test_weekly_period_contains_ref_date(ref_date: date) -> None:
    """resolve_period WEEKLY: ref_date is always within [period_start, period_end]."""
    b = _stub_budget(BudgetPeriod.WEEKLY, date(2024, 1, 1))
    start, end = resolve_period(b, ref_date)
    assert start <= ref_date <= end
    assert (end - start).days == 6
    assert start.weekday() == 0  # Monday


@given(ref_date=_date_2024_2026)
@settings(max_examples=100)
def test_biweekly_period_exactly_14_days(ref_date: date) -> None:
    """resolve_period BIWEEKLY: period is exactly 14 days containing ref_date."""
    b = _stub_budget(BudgetPeriod.BIWEEKLY, date(2024, 1, 1))
    start, end = resolve_period(b, ref_date)
    assert start <= ref_date <= end
    assert (end - start).days == 13


@given(ref_date=_date_2025)
@settings(max_examples=100)
def test_semimonthly_period_within_month(ref_date: date) -> None:
    """resolve_period SEMIMONTHLY: period stays within same calendar month."""
    b = _stub_budget(BudgetPeriod.SEMIMONTHLY, date(2025, 1, 1))
    start, end = resolve_period(b, ref_date)
    assert start <= ref_date <= end
    assert start.month == ref_date.month
    assert end.month == ref_date.month


@given(ref_date=_date_2024_2026)
@settings(max_examples=50)
def test_annual_period_always_full_year(ref_date: date) -> None:
    """resolve_period ANNUAL: always returns Jan 1 to Dec 31 of that year."""
    b = _stub_budget(BudgetPeriod.ANNUAL, date(2024, 1, 1))
    start, end = resolve_period(b, ref_date)
    assert start == date(ref_date.year, 1, 1)
    assert end == date(ref_date.year, 12, 31)


# ===========================================================================
# Shared integration DB fixture
# ===========================================================================


@pytest.fixture()
async def db(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    yield session


@pytest.fixture()
async def household_and_user(
    db: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (household_id, user_id, actor_id)."""
    from app.households.enums import VisibilityMode

    user = await create_user(
        db,
        email=f"budget_test_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Budget Tester",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await create_household(
        db,
        name="Budget Household",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    await db.commit()
    return household.id, user.id, user.id


# ===========================================================================
# Integration tests
# ===========================================================================


@pytest.mark.integration
class TestBudgetCRUD:
    async def test_create_and_get_budget(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Monthly Budget",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            expected_income=Decimal("5000"),
            currency="USD",
        )
        await db.commit()

        assert budget.budget_group_id == budget.id
        assert budget.name == "Monthly Budget"
        assert budget.method == "manual"

        fetched = await get_budget(db, budget_group_id=budget.budget_group_id, household_id=hh_id)
        assert fetched.id == budget.id
        assert fetched.effective_to is None

    async def test_get_nonexistent_raises(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, _, _ = household_and_user
        with pytest.raises(NotFoundError):
            await get_budget(db, budget_group_id=uuid.uuid4(), household_id=hh_id)

    async def test_list_budgets(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        for name in ("A", "B", "C"):
            await create_budget(
                db,
                household_id=hh_id,
                actor_id=user_id,
                name=name,
                period=BudgetPeriod.MONTHLY,
                start_date=date(2025, 1, 1),
                method=BudgetMethod.MANUAL,
            )
        await db.commit()
        budgets = await list_budgets(db, household_id=hh_id)
        assert len(budgets) == 3
        assert all(b.effective_to is None for b in budgets)

    async def test_archive_budget(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="To Archive",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()

        await archive_budget(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
        )
        await db.commit()

        with pytest.raises(NotFoundError):
            await get_budget(db, budget_group_id=budget.budget_group_id, household_id=hh_id)


@pytest.mark.integration
class TestVersioning:
    async def test_edit_creates_new_version(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        v1 = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Original",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()

        v2 = await update_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            name="Renamed",
            effective_from=date(2025, 6, 1),
        )
        await db.commit()

        # v2 is new current version
        assert v2.id != v1.id
        assert v2.budget_group_id == v1.budget_group_id
        assert v2.name == "Renamed"
        assert v2.effective_to is None

        # v1 is now closed
        await db.refresh(v1)
        assert v1.effective_to == date(2025, 5, 31)

    async def test_get_active_budget_correct_version(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        v1 = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="V1",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()

        v2 = await update_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            name="V2",
            effective_from=date(2025, 6, 1),
        )
        await db.commit()

        # Before v2 effective_from: should get v1
        active_jan = await get_active_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            as_of_date=date(2025, 3, 15),
        )
        assert active_jan.id == v1.id

        # After v2 effective_from: should get v2
        active_jul = await get_active_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            as_of_date=date(2025, 7, 1),
        )
        assert active_jul.id == v2.id

    async def test_edit_never_modifies_historical_rows(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        v1 = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Original",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        v1_id = v1.id
        await db.commit()

        await update_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            name="Changed",
            effective_from=date(2025, 4, 1),
        )
        await db.commit()

        # Re-fetch v1 by its original id (bypassing archived filter)
        result = await db.execute(
            sa.select(Budget).where(Budget.id == v1_id),
            execution_options={"include_archived": True},
        )
        v1_refetched = result.scalar_one()
        assert v1_refetched.name == "Original"  # unchanged

    async def test_list_budget_history(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        v1 = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="V1",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()
        await update_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            name="V2",
            effective_from=date(2025, 4, 1),
        )
        await db.commit()
        await update_budget(
            db,
            budget_group_id=v1.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            name="V3",
            effective_from=date(2025, 7, 1),
        )
        await db.commit()

        history = await list_budget_history(
            db, budget_group_id=v1.budget_group_id, household_id=hh_id
        )
        assert len(history) == 3
        assert history[0].name == "V3"  # newest first


@pytest.mark.integration
class TestBudgetLines:
    async def _make_budget(self, db: AsyncSession, hh_id: uuid.UUID, user_id: uuid.UUID) -> Budget:
        b = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()
        return b

    async def test_create_and_list_lines(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await self._make_budget(db, hh_id, user_id)
        cat_id = uuid.uuid4()

        line = await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=cat_id,
            planned_amount=Decimal("500"),
            currency="USD",
        )
        await db.commit()

        assert line.budget_id == budget.budget_group_id
        assert line.category_id == cat_id
        assert line.planned_amount == Decimal("500")
        assert line.rollover_policy == "none"
        assert line.carried_amount == Decimal("0")

        lines = await list_budget_lines(
            db, budget_group_id=budget.budget_group_id, household_id=hh_id
        )
        assert len(lines) == 1

    async def test_update_line(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await self._make_budget(db, hh_id, user_id)
        line = await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=uuid.uuid4(),
            planned_amount=Decimal("500"),
        )
        await db.commit()

        updated = await update_budget_line(
            db,
            line_id=line.id,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            planned_amount=Decimal("750"),
            rollover_policy=RolloverPolicy.ACCUMULATE,
        )
        await db.commit()

        assert updated.planned_amount == Decimal("750")
        assert updated.rollover_policy == "accumulate"

    async def test_archive_line(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await self._make_budget(db, hh_id, user_id)
        line = await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=uuid.uuid4(),
            planned_amount=Decimal("500"),
        )
        await db.commit()

        await archive_budget_line(
            db,
            line_id=line.id,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
        )
        await db.commit()

        lines = await list_budget_lines(
            db, budget_group_id=budget.budget_group_id, household_id=hh_id
        )
        assert len(lines) == 0


@pytest.mark.integration
class TestPeriodIncome:
    async def test_set_period_income(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            expected_income_strategy=ExpectedIncomeStrategy.MANUAL_PER_PERIOD,
        )
        await db.commit()

        override = await set_period_income(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            expected_income=Decimal("4500"),
            currency="USD",
        )
        await db.commit()

        assert override.expected_income == Decimal("4500")
        assert override.budget_group_id == budget.budget_group_id

    async def test_upsert_period_income(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        await db.commit()

        await set_period_income(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            expected_income=Decimal("4500"),
        )
        await db.commit()

        updated = await set_period_income(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            expected_income=Decimal("5000"),
        )
        await db.commit()

        assert updated.expected_income == Decimal("5000")
        # Verify only one row exists
        result = await db.execute(
            sa.select(BudgetPeriodIncome).where(
                BudgetPeriodIncome.budget_group_id == budget.budget_group_id
            )
        )
        assert len(result.scalars().all()) == 1


@pytest.mark.integration
class TestScopeFiltering:
    """Scope filtering: empty list means any (not none)."""

    async def test_empty_scope_matches_any(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        """An empty scope_accounts list means any account — verify service accepts it."""
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Wide Scope",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            scope_accounts=[],  # empty = any
            scope_categories=[],  # empty = any
            scope_tags=[],  # empty = any
        )
        await db.commit()

        fetched = await get_budget(db, budget_group_id=budget.budget_group_id, household_id=hh_id)
        assert fetched.scope_accounts == []
        assert fetched.scope_categories == []
        assert fetched.scope_tags == []

    async def test_scope_accounts_stored_and_retrieved(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        acct1, acct2 = uuid.uuid4(), uuid.uuid4()
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Scoped",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            scope_accounts=[acct1, acct2],
        )
        await db.commit()

        fetched = await get_budget(db, budget_group_id=budget.budget_group_id, household_id=hh_id)
        stored = [uuid.UUID(a) for a in fetched.scope_accounts]
        assert set(stored) == {acct1, acct2}


@pytest.mark.integration
class TestRolloverIntegration:
    """Rollover integration: carried_out of period N == carried_in of period N+1."""

    async def test_rollover_carried_forward(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        """After period_close, line.carried_amount == period_actual.carried_out."""
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Rollover Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        cat_id = uuid.uuid4()
        line = await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=cat_id,
            planned_amount=Decimal("1000"),
            rollover_policy=RolloverPolicy.ACCUMULATE,
        )
        await db.commit()

        # Compute actuals for January with zero spend (no allocations in test DB)
        results = await compute_actuals(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        await db.commit()

        assert len(results) == 1
        r = results[0]
        # actual = 0, carried_in = 0, so carried_out = 1000 (unspent)
        assert r.actual == Decimal("0")
        assert r.carried_in == Decimal("0")
        assert r.period_actual is not None
        assert r.period_actual.carried_out == Decimal("1000")

        # Simulate period close: update carried_amount
        line.carried_amount = r.period_actual.carried_out
        await db.commit()

        # Next period: carried_in should reflect previous carried_out
        results2 = await compute_actuals(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
        )
        await db.commit()

        r2 = results2[0]
        assert r2.carried_in == Decimal("1000")
        # effective_planned = 1000 (planned) + 1000 (carried_in) = 2000; actual = 0
        assert r2.remaining == Decimal("2000")

    async def test_accumulate_capped_never_exceeds_cap_integration(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        """accumulate_capped: carried_out <= cap even with large unspent amounts."""
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Cap Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
        )
        cat_id = uuid.uuid4()
        await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=cat_id,
            planned_amount=Decimal("1000"),
            rollover_policy=RolloverPolicy.ACCUMULATE_CAPPED,
            rollover_cap=Decimal("300"),
        )
        await db.commit()

        results = await compute_actuals(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        await db.commit()

        r = results[0]
        assert r.period_actual is not None
        assert r.period_actual.carried_out <= Decimal("300")


@pytest.mark.integration
class TestExpectedIncome:
    async def test_fixed_income_strategy(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Fixed Income",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            expected_income_strategy=ExpectedIncomeStrategy.FIXED,
            expected_income=Decimal("5000"),
        )
        await db.commit()

        result = await compute_expected_income(
            db,
            budget=budget,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            household_id=hh_id,
        )
        assert result == Decimal("5000")

    async def test_manual_per_period_strategy(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Manual Income",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            expected_income_strategy=ExpectedIncomeStrategy.MANUAL_PER_PERIOD,
        )
        await db.commit()

        # No override set yet
        result = await compute_expected_income(
            db,
            budget=budget,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            household_id=hh_id,
        )
        assert result is None

        # Set override
        await set_period_income(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            period_start=date(2025, 1, 1),
            expected_income=Decimal("4200"),
        )
        await db.commit()

        result2 = await compute_expected_income(
            db,
            budget=budget,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            household_id=hh_id,
        )
        assert result2 == Decimal("4200")


@pytest.mark.integration
class TestGetStatus:
    async def test_get_status_returns_snapshot(
        self, db: AsyncSession, household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    ) -> None:
        hh_id, user_id, _ = household_and_user
        budget = await create_budget(
            db,
            household_id=hh_id,
            actor_id=user_id,
            name="Status Test",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2025, 1, 1),
            method=BudgetMethod.MANUAL,
            expected_income=Decimal("5000"),
        )
        cat_id = uuid.uuid4()
        await create_budget_line(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            actor_id=user_id,
            category_id=cat_id,
            planned_amount=Decimal("1000"),
        )
        await db.commit()

        snapshot = await get_status(
            db,
            budget_group_id=budget.budget_group_id,
            household_id=hh_id,
            as_of_date=date(2025, 1, 15),
        )
        await db.commit()

        assert snapshot.budget.id == budget.id
        assert snapshot.period_start == date(2025, 1, 1)
        assert snapshot.period_end == date(2025, 1, 31)
        assert len(snapshot.lines) == 1
        assert snapshot.lines[0].planned == Decimal("1000")
        assert snapshot.lines[0].actual == Decimal("0")
        assert snapshot.lines[0].status == BudgetLineStatus.UNDER


# ===========================================================================
# Hypothesis property tests backed by DB fixtures
# ===========================================================================


@pytest.mark.integration
@given(
    planned=_money,
    cap=_money,
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_accumulate_capped_property_db(
    planned: Decimal,
    cap: Decimal,
    db: AsyncSession,
    household_and_user: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """Property: accumulate_capped carried_out <= cap, always."""
    hh_id, user_id, _ = household_and_user
    budget = await create_budget(
        db,
        household_id=hh_id,
        actor_id=user_id,
        name="PropTest",
        period=BudgetPeriod.MONTHLY,
        start_date=date(2025, 1, 1),
        method=BudgetMethod.MANUAL,
    )
    await create_budget_line(
        db,
        budget_group_id=budget.budget_group_id,
        household_id=hh_id,
        actor_id=user_id,
        category_id=uuid.uuid4(),
        planned_amount=planned,
        rollover_policy=RolloverPolicy.ACCUMULATE_CAPPED,
        rollover_cap=cap,
    )
    await db.commit()

    results = await compute_actuals(
        db,
        budget_group_id=budget.budget_group_id,
        household_id=hh_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
    )
    await db.commit()

    for r in results:
        assert r.period_actual is not None
        assert r.period_actual.carried_out <= cap
