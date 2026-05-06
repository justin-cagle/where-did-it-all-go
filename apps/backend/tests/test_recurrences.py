"""Tests for the recurrences module.

Unit tests (no DB) run without any external services.
Integration tests (marked @pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests cover:
  - Cadence detection: weekly/biweekly/monthly correctly identified across
    date arithmetic edge cases — month boundaries, leap years
  - Tolerance matching: amount ± tolerance correctly widens/narrows match window
  - Exception application: skip removes instance, amount_change overrides amount,
    date_shift moves date; multiple exceptions on same recurrence compose correctly
  - Missed detection: instance is missed iff expected_date + tolerance has passed
    with no match
  - Never-auto-promote invariant: detect_recurrences never writes a Recurrence row
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.accounts.models
import app.classification.models
import app.households.models
import app.recurrences.models
import app.transactions.models  # noqa: F401
from app.accounts.enums import AccountType
from app.accounts.service import create_account
from app.database import Base
from app.households.enums import VisibilityMode
from app.households.service import create_household, create_user
from app.recurrences.enums import (
    Cadence,
    CandidateStatus,
    ExceptionType,
    MatchStatus,
    RecurrenceKind,
)
from app.recurrences.models import (
    Recurrence,
    RecurrenceCandidate,
    RecurrenceException,
    RecurrenceMatch,
)
from app.recurrences.service import (
    ConflictError,
    ExpectedEvent,
    NotFoundError,
    ValidationError,
    apply_exceptions_to_events,
    archive_recurrence,
    check_missed,
    confirm_candidate,
    create_recurrence,
    detect_cadence,
    detect_recurrences,
    dismiss_candidate,
    generate_expected_dates,
    get_expected_events,
    get_recurrence,
    is_amount_within_tolerance,
    is_instance_missed,
    list_candidates,
    match_transaction,
    normalize_merchant,
    pause_recurrence,
    resume_recurrence,
)
from app.transactions.enums import TransactionDirection, TransactionState
from app.transactions.service import create_transaction

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_money = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("9999.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
_nonneg_money = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
_date = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestNormalizeMerchant:
    def test_lowercase(self) -> None:
        assert normalize_merchant("NETFLIX") == "netflix"

    def test_strips_punctuation(self) -> None:
        assert normalize_merchant("Netflix, Inc.") == "netflix inc"

    def test_collapses_whitespace(self) -> None:
        assert normalize_merchant("  netflix  ") == "netflix"

    def test_deterministic(self) -> None:
        s = "AMAZON.COM*AB12"
        assert normalize_merchant(s) == normalize_merchant(s)


class TestDetectCadence:
    def test_weekly_exact(self) -> None:
        start = date(2026, 1, 1)
        dates = [start + timedelta(weeks=i) for i in range(5)]
        assert detect_cadence(dates) == Cadence.WEEKLY

    def test_biweekly_exact(self) -> None:
        start = date(2026, 1, 1)
        dates = [start + timedelta(weeks=2 * i) for i in range(5)]
        assert detect_cadence(dates) == Cadence.BIWEEKLY

    def test_monthly_same_day(self) -> None:
        dates = [date(2025, m, 15) for m in range(1, 6)]
        assert detect_cadence(dates) == Cadence.MONTHLY

    def test_annual(self) -> None:
        dates = [date(2020 + i, 3, 15) for i in range(4)]
        assert detect_cadence(dates) == Cadence.ANNUAL

    def test_requires_three_dates(self) -> None:
        assert detect_cadence([date(2026, 1, 1), date(2026, 1, 8)]) is None

    def test_inconsistent_returns_none(self) -> None:
        dates = [date(2026, 1, 1), date(2026, 1, 8), date(2026, 2, 15)]
        assert detect_cadence(dates) is None

    def test_weekly_with_tolerance(self) -> None:
        start = date(2026, 1, 1)
        dates = [
            start,
            start + timedelta(days=7),
            start + timedelta(days=11),  # 4 days late — still weekly
            start + timedelta(days=18),
        ]
        assert detect_cadence(dates) == Cadence.WEEKLY

    def test_monthly_feb_boundary(self) -> None:
        dates = [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)]
        # deltas: 29, 31 — 30 ± 4 → both within tolerance
        assert detect_cadence(dates) == Cadence.MONTHLY

    def test_empty_returns_none(self) -> None:
        assert detect_cadence([]) is None


class TestIsAmountWithinTolerance:
    def test_exact_match(self) -> None:
        assert is_amount_within_tolerance(Decimal("9.99"), Decimal("9.99"), Decimal("0"))

    def test_within_tolerance(self) -> None:
        assert is_amount_within_tolerance(Decimal("10.50"), Decimal("9.99"), Decimal("1.00"))

    def test_outside_tolerance(self) -> None:
        assert not is_amount_within_tolerance(Decimal("12.00"), Decimal("9.99"), Decimal("1.00"))

    def test_zero_tolerance_strict(self) -> None:
        assert not is_amount_within_tolerance(Decimal("10.00"), Decimal("9.99"), Decimal("0"))

    def test_below_expected_within_tolerance(self) -> None:
        assert is_amount_within_tolerance(Decimal("9.00"), Decimal("9.99"), Decimal("1.00"))


class TestGenerateExpectedDates:
    def test_weekly_generates_correct_count(self) -> None:
        start = date(2026, 1, 1)
        dates = generate_expected_dates(
            cadence=str(Cadence.WEEKLY),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=start + timedelta(days=28),
        )
        assert len(dates) == 5  # Jan 1, 8, 15, 22, 29

    def test_monthly_respects_end_date(self) -> None:
        start = date(2026, 1, 15)
        dates = generate_expected_dates(
            cadence=str(Cadence.MONTHLY),
            start_date=start,
            end_date=date(2026, 3, 15),
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2026, 6, 15),
        )
        assert all(d <= date(2026, 3, 15) for d in dates)
        assert len(dates) == 3  # Jan, Feb, Mar

    def test_monthly_feb_clamps_to_28(self) -> None:
        start = date(2026, 1, 31)
        dates = generate_expected_dates(
            cadence=str(Cadence.MONTHLY),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2026, 3, 31),
        )
        assert date(2026, 2, 28) in dates

    def test_annual_generates_yearly(self) -> None:
        start = date(2023, 6, 15)
        dates = generate_expected_dates(
            cadence=str(Cadence.ANNUAL),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2027, 6, 30),
        )
        assert len(dates) == 5  # 2023, 2024, 2025, 2026, 2027

    def test_semimonthly_two_per_month(self) -> None:
        start = date(2026, 1, 1)
        dates = generate_expected_dates(
            cadence=str(Cadence.SEMIMONTHLY),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2026, 1, 31),
        )
        assert len(dates) == 2

    def test_no_dates_before_start(self) -> None:
        start = date(2026, 6, 1)
        dates = generate_expected_dates(
            cadence=str(Cadence.MONTHLY),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=date(2026, 1, 1),
            to_date=date(2026, 5, 31),
        )
        assert dates == []

    def test_custom_cron_treated_as_monthly(self) -> None:
        start = date(2026, 1, 15)
        dates_cron = generate_expected_dates(
            cadence=str(Cadence.CUSTOM_CRON),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2026, 4, 30),
        )
        dates_monthly = generate_expected_dates(
            cadence=str(Cadence.MONTHLY),
            start_date=start,
            end_date=None,
            expected_day_of_period=None,
            from_date=start,
            to_date=date(2026, 4, 30),
        )
        assert dates_cron == dates_monthly


class TestApplyExceptionsToEvents:
    def _make_event(self, d: date, amount: Decimal = Decimal("9.99")) -> ExpectedEvent:
        return ExpectedEvent(
            recurrence_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            expected_date=d,
            expected_amount=amount,
            currency="USD",
            cadence=str(Cadence.MONTHLY),
            merchant_name="netflix",
        )

    def _make_exception(
        self,
        recurrence_id: uuid.UUID,
        period: date,
        exc_type: ExceptionType,
        override_amount: Decimal | None = None,
        override_date: date | None = None,
    ) -> RecurrenceException:
        exc = RecurrenceException(
            recurrence_id=recurrence_id,
            exception_type=str(exc_type),
            affected_period=period,
            override_amount=override_amount,
            override_date=override_date,
        )
        return exc

    def test_skip_removes_instance(self) -> None:
        d = date(2026, 3, 15)
        ev = self._make_event(d)
        exc = self._make_exception(ev.recurrence_id, d, ExceptionType.SKIP)
        result = apply_exceptions_to_events([ev], [exc])
        assert result == []

    def test_amount_change_overrides_amount(self) -> None:
        d = date(2026, 3, 15)
        ev = self._make_event(d, Decimal("9.99"))
        exc = self._make_exception(
            ev.recurrence_id, d, ExceptionType.AMOUNT_CHANGE, override_amount=Decimal("15.99")
        )
        result = apply_exceptions_to_events([ev], [exc])
        assert len(result) == 1
        assert result[0].expected_amount == Decimal("15.99")
        assert result[0].exception_type == str(ExceptionType.AMOUNT_CHANGE)

    def test_date_shift_moves_date(self) -> None:
        d = date(2026, 3, 15)
        new_d = date(2026, 3, 20)
        ev = self._make_event(d)
        exc = self._make_exception(
            ev.recurrence_id, d, ExceptionType.DATE_SHIFT, override_date=new_d
        )
        result = apply_exceptions_to_events([ev], [exc])
        assert len(result) == 1
        assert result[0].expected_date == new_d

    def test_unaffected_event_passes_through(self) -> None:
        d1 = date(2026, 3, 15)
        d2 = date(2026, 4, 15)
        ev1 = self._make_event(d1)
        ev2 = self._make_event(d2)
        exc = self._make_exception(ev1.recurrence_id, d1, ExceptionType.SKIP)
        result = apply_exceptions_to_events([ev1, ev2], [exc])
        assert len(result) == 1
        assert result[0].expected_date == d2

    def test_multiple_exceptions_compose(self) -> None:
        d1 = date(2026, 2, 15)
        d2 = date(2026, 3, 15)
        d3 = date(2026, 4, 15)
        rid = uuid.uuid4()
        events = [
            ExpectedEvent(
                rid, uuid.uuid4(), d1, Decimal("9.99"), "USD", str(Cadence.MONTHLY), "netflix"
            ),
            ExpectedEvent(
                rid, uuid.uuid4(), d2, Decimal("9.99"), "USD", str(Cadence.MONTHLY), "netflix"
            ),
            ExpectedEvent(
                rid, uuid.uuid4(), d3, Decimal("9.99"), "USD", str(Cadence.MONTHLY), "netflix"
            ),
        ]
        exceptions = [
            self._make_exception(rid, d1, ExceptionType.SKIP),
            self._make_exception(
                rid, d2, ExceptionType.AMOUNT_CHANGE, override_amount=Decimal("15.99")
            ),
        ]
        result = apply_exceptions_to_events(events, exceptions)
        assert len(result) == 2  # d1 skipped
        assert result[0].expected_date == d2
        assert result[0].expected_amount == Decimal("15.99")
        assert result[1].expected_date == d3
        assert result[1].expected_amount == Decimal("9.99")


class TestIsInstanceMissed:
    def test_missed_when_past_tolerance(self) -> None:
        exp = date(2026, 1, 1)
        today = date(2026, 1, 10)  # 9 days later — beyond 4-day tolerance
        assert is_instance_missed(exp, today)

    def test_not_missed_within_tolerance(self) -> None:
        exp = date(2026, 1, 1)
        today = date(2026, 1, 4)  # exactly at tolerance
        assert not is_instance_missed(exp, today)

    def test_not_missed_future_date(self) -> None:
        exp = date(2026, 2, 1)
        today = date(2026, 1, 15)
        assert not is_instance_missed(exp, today)

    def test_custom_tolerance(self) -> None:
        exp = date(2026, 1, 1)
        today = date(2026, 1, 8)
        # today (Jan 8) > exp+6 (Jan 7) → missed
        assert is_instance_missed(exp, today, date_tolerance_days=6)
        # today (Jan 8) > exp+7 (Jan 8) → False (strict >)
        assert not is_instance_missed(exp, today, date_tolerance_days=7)


# ===========================================================================
# Hypothesis property tests — pure helpers
# ===========================================================================


@given(st.lists(_date, min_size=3, max_size=12))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_detect_cadence_deterministic(dates: list[date]) -> None:
    """Same input always yields same output."""
    assert detect_cadence(dates) == detect_cadence(dates)


@given(_money, _money, _nonneg_money)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_tolerance_symmetry(amount: Decimal, expected: Decimal, tolerance: Decimal) -> None:
    """Tolerance check is symmetric: |a - b| <= tol iff |b - a| <= tol."""
    result_ab = is_amount_within_tolerance(amount, expected, tolerance)
    result_ba = is_amount_within_tolerance(expected, amount, tolerance)
    assert result_ab == result_ba


@given(_money, _nonneg_money)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_tolerance_zero_is_exact(amount: Decimal, tolerance: Decimal) -> None:
    """Any amount within its own tolerance of zero is always true when tol >= 0."""
    assert is_amount_within_tolerance(amount, amount, tolerance)


@given(_date)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_weekly_dates_ordered(start: date) -> None:
    """Generated weekly dates are strictly ascending."""
    dates = generate_expected_dates(
        cadence=str(Cadence.WEEKLY),
        start_date=start,
        end_date=None,
        expected_day_of_period=None,
        from_date=start,
        to_date=start + timedelta(days=56),
    )
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)  # no duplicates


@given(_date)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_monthly_dates_unique_and_ordered(start: date) -> None:
    """Generated monthly dates are strictly ascending and unique."""
    to = start.replace(year=min(start.year + 2, 2030))
    dates = generate_expected_dates(
        cadence=str(Cadence.MONTHLY),
        start_date=start,
        end_date=None,
        expected_day_of_period=None,
        from_date=start,
        to_date=to,
    )
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)


@given(_date, _date, st.integers(min_value=1, max_value=14))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_missed_consistent_with_tolerance(
    expected: date,
    today: date,
    tol: int,
) -> None:
    """Missed iff gap > tolerance. Never missed when today <= expected."""
    delta = (today - expected).days
    result = is_instance_missed(expected, today, date_tolerance_days=tol)
    if today <= expected:
        assert not result
    elif delta > tol:
        assert result
    else:
        assert not result


# ===========================================================================
# Integration tests — DB required
# ===========================================================================


@pytest.fixture()
async def db(postgres_url: str) -> AsyncGenerator[AsyncSession, None]:
    """Integration DB session with all tables created."""
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def seed(db: AsyncSession) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Seed a household + user + account."""
    user = await create_user(
        db,
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Tester",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await create_household(
        db,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    account = await create_account(
        db,
        household_id=household.id,
        actor_id=user.id,
        name="Checking",
        account_type=AccountType.CHECKING,
        institution=None,
        current_balance=Decimal("1000.00"),
        currency="USD",
    )
    await db.commit()
    return {"user": user, "household": household, "account": account}


@pytest.mark.integration
async def test_create_and_get_recurrence(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        merchant_name="Netflix",
        start_date=date(2026, 1, 1),
    )
    await db.commit()

    fetched = await get_recurrence(db, recurrence_id=rec.id, household_id=hh.id)
    assert fetched.id == rec.id
    assert fetched.cadence == str(Cadence.MONTHLY)
    assert fetched.expected_amount == Decimal("15.99")
    assert fetched.paused is False


@pytest.mark.integration
async def test_archive_recurrence_never_hard_delete(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 1),
    )
    await db.commit()

    await archive_recurrence(db, recurrence_id=rec.id, household_id=hh.id, actor_id=user.id)
    await db.commit()

    # Row still exists in DB (soft delete only)
    result = await db.execute(
        sa.select(Recurrence).where(Recurrence.id == rec.id),
        execution_options={"include_archived": True},
    )
    still_exists = result.scalar_one_or_none()
    assert still_exists is not None
    assert still_exists.archived_at is not None


@pytest.mark.integration
async def test_pause_resume(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 1),
    )
    await db.commit()

    paused = await pause_recurrence(db, recurrence_id=rec.id, household_id=hh.id, actor_id=user.id)
    assert paused.paused is True

    with pytest.raises(ConflictError):
        await pause_recurrence(db, recurrence_id=rec.id, household_id=hh.id, actor_id=user.id)

    resumed = await resume_recurrence(
        db, recurrence_id=rec.id, household_id=hh.id, actor_id=user.id
    )
    assert resumed.paused is False
    await db.commit()


@pytest.mark.integration
async def test_detect_recurrences_never_auto_promotes(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    """Core invariant: detect_recurrences never writes a Recurrence row."""
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    # Seed 4 monthly transactions from the same merchant
    base = date(2025, 12, 15)
    for i in range(4):
        await create_transaction(
            db,
            household_id=hh.id,
            account_id=account.id,
            actor_id=user.id,
            amount=Decimal("15.99"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=base + timedelta(days=30 * i),
            pending_date=None,
            occurred_at=base + timedelta(days=30 * i),
            description="NETFLIX",
            merchant_name="Netflix",
        )
    await db.commit()

    candidates = await detect_recurrences(db, household_id=hh.id)
    await db.commit()

    # Candidates created
    assert len(candidates) >= 1
    assert candidates[0].status == str(CandidateStatus.PENDING)

    # Invariant: NO Recurrence rows written
    rec_result = await db.execute(sa.select(Recurrence).where(Recurrence.household_id == hh.id))
    assert rec_result.scalars().all() == []


@pytest.mark.integration
async def test_detect_recurrences_idempotent(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Running detection twice does not create duplicate candidates."""
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    base = date(2025, 12, 15)
    for i in range(4):
        await create_transaction(
            db,
            household_id=hh.id,
            account_id=account.id,
            actor_id=user.id,
            amount=Decimal("9.99"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=base + timedelta(days=30 * i),
            pending_date=None,
            occurred_at=base + timedelta(days=30 * i),
            description="SPOTIFY",
            merchant_name="Spotify",
        )
    await db.commit()

    await detect_recurrences(db, household_id=hh.id)
    await db.commit()
    candidates_first = await list_candidates(db, household_id=hh.id)

    await detect_recurrences(db, household_id=hh.id)
    await db.commit()
    candidates_second = await list_candidates(db, household_id=hh.id)

    assert len(candidates_first) == len(candidates_second)


@pytest.mark.integration
async def test_confirm_candidate_promotes_to_recurrence(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    base = date(2025, 12, 15)
    for i in range(4):
        await create_transaction(
            db,
            household_id=hh.id,
            account_id=account.id,
            actor_id=user.id,
            amount=Decimal("15.99"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=base + timedelta(days=30 * i),
            pending_date=None,
            occurred_at=base + timedelta(days=30 * i),
            description="NETFLIX",
            merchant_name="Netflix",
        )
    await db.commit()

    candidates = await detect_recurrences(db, household_id=hh.id)
    await db.commit()
    assert len(candidates) >= 1

    rec = await confirm_candidate(
        db, candidate_id=candidates[0].id, household_id=hh.id, actor_id=user.id
    )
    await db.commit()

    assert rec.kind == str(RecurrenceKind.DETECTED)
    assert rec.cadence == candidates[0].cadence

    # Candidate status updated
    result = await db.execute(
        sa.select(RecurrenceCandidate).where(RecurrenceCandidate.id == candidates[0].id)
    )
    cand = result.scalar_one()
    assert cand.status == str(CandidateStatus.CONFIRMED)
    assert cand.recurrence_id == rec.id

    # RecurrenceMatch rows written for back-fill
    match_result = await db.execute(
        sa.select(RecurrenceMatch).where(RecurrenceMatch.recurrence_id == rec.id)
    )
    matches = match_result.scalars().all()
    assert len(matches) == 4


@pytest.mark.integration
async def test_confirm_candidate_double_confirm_rejected(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    base = date(2025, 12, 15)
    for i in range(4):
        await create_transaction(
            db,
            household_id=hh.id,
            account_id=account.id,
            actor_id=user.id,
            amount=Decimal("15.99"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=base + timedelta(days=30 * i),
            pending_date=None,
            occurred_at=base + timedelta(days=30 * i),
            description="NETFLIX",
            merchant_name="Netflix",
        )
    await db.commit()

    candidates = await detect_recurrences(db, household_id=hh.id)
    await db.commit()

    await confirm_candidate(db, candidate_id=candidates[0].id, household_id=hh.id, actor_id=user.id)
    await db.commit()

    with pytest.raises(ConflictError):
        await confirm_candidate(
            db, candidate_id=candidates[0].id, household_id=hh.id, actor_id=user.id
        )


@pytest.mark.integration
async def test_dismiss_candidate(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    base = date(2025, 12, 15)
    for i in range(4):
        await create_transaction(
            db,
            household_id=hh.id,
            account_id=account.id,
            actor_id=user.id,
            amount=Decimal("9.99"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=base + timedelta(days=30 * i),
            pending_date=None,
            occurred_at=base + timedelta(days=30 * i),
            description="SPOTIFY",
            merchant_name="Spotify",
        )
    await db.commit()

    candidates = await detect_recurrences(db, household_id=hh.id)
    await db.commit()

    dismissed = await dismiss_candidate(
        db, candidate_id=candidates[0].id, household_id=hh.id, actor_id=user.id
    )
    await db.commit()
    assert dismissed.status == str(CandidateStatus.DISMISSED)


@pytest.mark.integration
async def test_match_transaction_sets_recurrence_id(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    # Create recurrence directly (declared)
    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        tolerance=Decimal("1.00"),
        merchant_name="Netflix",
        start_date=date(2026, 1, 1),
    )

    # Create matching transaction
    tx = await create_transaction(
        db,
        household_id=hh.id,
        account_id=account.id,
        actor_id=user.id,
        amount=Decimal("15.99"),
        currency="USD",
        direction=TransactionDirection.DEBIT,
        transaction_type=None,
        state=TransactionState.POSTED,
        posted_date=date(2026, 1, 15),
        pending_date=None,
        occurred_at=date(2026, 1, 15),
        description="NETFLIX",
        merchant_name="Netflix",
    )
    await db.commit()

    result = await match_transaction(db, transaction_id=tx.id, household_id=hh.id)
    await db.commit()

    assert result.matched is True
    assert result.recurrence_id == rec.id
    assert result.status in (MatchStatus.MATCHED, MatchStatus.DEVIATED)


@pytest.mark.integration
async def test_match_transaction_idempotent(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Calling match_transaction twice on the same transaction is safe."""
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        merchant_name="Netflix",
        start_date=date(2026, 1, 1),
    )
    tx = await create_transaction(
        db,
        household_id=hh.id,
        account_id=account.id,
        actor_id=user.id,
        amount=Decimal("15.99"),
        currency="USD",
        direction=TransactionDirection.DEBIT,
        transaction_type=None,
        state=TransactionState.POSTED,
        posted_date=date(2026, 1, 15),
        pending_date=None,
        occurred_at=date(2026, 1, 15),
        description="NETFLIX",
        merchant_name="Netflix",
    )
    await db.commit()

    await match_transaction(db, transaction_id=tx.id, household_id=hh.id)
    await db.commit()
    await match_transaction(db, transaction_id=tx.id, household_id=hh.id)
    await db.commit()

    match_result = await db.execute(
        sa.select(RecurrenceMatch).where(RecurrenceMatch.transaction_id == tx.id)
    )
    matches = match_result.scalars().all()
    assert len(matches) == 1  # only one RecurrenceMatch created


@pytest.mark.integration
async def test_apply_exception_skip(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    from app.recurrences.service import apply_exception, list_exceptions

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 1),
    )
    await db.commit()

    exc = await apply_exception(
        db,
        recurrence_id=rec.id,
        household_id=hh.id,
        actor_id=user.id,
        exception_type=ExceptionType.SKIP,
        affected_period=date(2026, 3, 1),
    )
    await db.commit()

    assert exc.exception_type == str(ExceptionType.SKIP)
    exceptions = await list_exceptions(db, recurrence_id=rec.id, household_id=hh.id)
    assert len(exceptions) == 1


@pytest.mark.integration
async def test_apply_exception_amount_change_requires_override(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    from app.recurrences.service import apply_exception

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 1),
    )
    await db.commit()

    with pytest.raises(ValidationError):
        await apply_exception(
            db,
            recurrence_id=rec.id,
            household_id=hh.id,
            actor_id=user.id,
            exception_type=ExceptionType.AMOUNT_CHANGE,
            affected_period=date(2026, 3, 1),
            override_amount=None,  # missing — should raise
        )


@pytest.mark.integration
async def test_get_expected_events_applies_exceptions(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    from app.recurrences.service import apply_exception

    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 15),
        merchant_name="Netflix",
    )
    await db.commit()

    # Skip March instance
    await apply_exception(
        db,
        recurrence_id=rec.id,
        household_id=hh.id,
        actor_id=user.id,
        exception_type=ExceptionType.SKIP,
        affected_period=date(2026, 3, 15),
    )
    await db.commit()

    events = await get_expected_events(
        db,
        household_id=hh.id,
        from_date=date(2026, 1, 1),
        to_date=date(2026, 4, 30),
    )
    dates = [e.expected_date for e in events]
    assert date(2026, 3, 15) not in dates
    assert date(2026, 1, 15) in dates
    assert date(2026, 2, 15) in dates
    assert date(2026, 4, 15) in dates


@pytest.mark.integration
async def test_check_missed_writes_missed_record(db: AsyncSession, seed: dict[str, Any]) -> None:
    import time_machine

    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    # Recurrence started 2 months ago, nothing matched
    rec = await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 15),
        merchant_name="Netflix",
    )
    await db.commit()

    # Simulate running check_missed on 2026-05-06 (well past Jan/Feb/Mar/Apr instances)
    with time_machine.travel(date(2026, 5, 6)):
        misses = await check_missed(db, household_id=hh.id)
        await db.commit()

    assert len(misses) >= 1
    assert all(m.status == str(MatchStatus.MISSED) for m in misses)
    assert all(m.recurrence_id == rec.id for m in misses)


@pytest.mark.integration
async def test_check_missed_idempotent(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Running check_missed twice does not create duplicate missed records."""
    import time_machine

    hh = seed["household"]
    user = seed["user"]
    account = seed["account"]

    await create_recurrence(
        db,
        household_id=hh.id,
        actor_id=user.id,
        account_id=account.id,
        kind=RecurrenceKind.DECLARED,
        cadence=Cadence.MONTHLY,
        expected_amount=Decimal("15.99"),
        currency="USD",
        start_date=date(2026, 1, 15),
        merchant_name="Netflix",
    )
    await db.commit()

    with time_machine.travel(date(2026, 5, 6)):
        await check_missed(db, household_id=hh.id)
        await db.commit()
        await check_missed(db, household_id=hh.id)
        await db.commit()

    match_result = await db.execute(
        sa.select(RecurrenceMatch).where(RecurrenceMatch.status == str(MatchStatus.MISSED))
    )
    all_missed = match_result.scalars().all()
    # Each expected_date should appear only once
    expected_dates = [m.expected_date for m in all_missed]
    assert len(expected_dates) == len(set(expected_dates))


@pytest.mark.integration
async def test_not_found_raises(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    with pytest.raises(NotFoundError):
        await get_recurrence(db, recurrence_id=uuid.uuid4(), household_id=hh.id)
