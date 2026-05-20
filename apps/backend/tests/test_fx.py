"""Tests for app.platform.fx — FX rate service.

Unit tests (no DB) cover identity and same-currency short-circuits.
Integration tests (@pytest.mark.integration) require Docker via testcontainers.
Hypothesis property tests verify the conversion formula stays within rounding tolerance.
"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import AsyncMock

import pytest
import respx
import sqlalchemy as sa
from httpx import Response
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service as accounts_service
from app.accounts.enums import AccountType
from app.households import service as households_service
from app.households.enums import VisibilityMode
from app.platform.fx import (
    _FRANKFURTER_BASE,
    FxRate,
    FXRateUnavailableError,
    _db_exact,
    _upsert_rate,
    convert,
    fetch_and_store_rates,
    get_rate,
)
from app.transactions import service as tx_service
from app.transactions.enums import TransactionDirection, TransactionState, TransactionType


async def _make_household_and_account(
    session: AsyncSession,
    *,
    home_currency: str = "USD",
    account_currency: str = "USD",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user = await households_service.create_user(
        session,
        email=f"fx_{uuid.uuid4().hex[:6]}@test.com",
        display_name="FX Tester",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await households_service.create_household(
        session,
        name="FX Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency=home_currency,
        owner=user,
    )
    account = await accounts_service.create_account(
        session,
        household_id=household.id,
        actor_id=user.id,
        name="FX Account",
        institution=None,
        account_type=AccountType.CHECKING,
        currency=account_currency,
        current_balance=Decimal("1000.00"),
    )
    return user.id, household.id, account.id


def _tx_kwargs(
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    currency: str = "USD",
    home_currency: str | None = None,
    occurred_at: date = date(2026, 1, 15),
    amount: Decimal = Decimal("100.00"),
) -> dict:
    return {
        "household_id": household_id,
        "account_id": account_id,
        "actor_id": actor_id,
        "amount": amount,
        "currency": currency,
        "direction": TransactionDirection.DEBIT,
        "transaction_type": TransactionType.REGULAR,
        "state": TransactionState.PENDING,
        "posted_date": occurred_at,
        "pending_date": None,
        "occurred_at": occurred_at,
        "description": "FX test transaction",
        "merchant_name": None,
        "external_id": None,
        "home_currency": home_currency,
    }


# ===========================================================================
# Unit tests -- no DB, no HTTP
# ===========================================================================


class TestSameCurrencyShortCircuit:
    async def test_get_rate_same_currency_returns_one(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        rate, is_approx = await get_rate("USD", "USD", date(2026, 1, 15), mock_session)
        assert rate == Decimal("1.0")
        assert is_approx is False
        mock_session.execute.assert_not_called()

    async def test_get_rate_case_insensitive(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        rate, is_approx = await get_rate("usd", "USD", date(2026, 1, 15), mock_session)
        assert rate == Decimal("1.0")
        assert is_approx is False

    async def test_convert_same_currency_identity(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        amount = Decimal("123.4567")
        result, is_approx = await convert(amount, "EUR", "EUR", date(2026, 1, 15), mock_session)
        assert result == amount
        assert is_approx is False
        mock_session.execute.assert_not_called()

    async def test_convert_same_currency_case_insensitive(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        result, _ = await convert(Decimal("50.00"), "eur", "EUR", date(2026, 1, 15), mock_session)
        assert result == Decimal("50.00")


class TestFetchAndStoreRatesEarlyReturn:
    async def test_empty_targets_list(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        # Any unregistered HTTP call raises in respx.mock(); proves no HTTP made
        with respx.mock(assert_all_mocked=True):
            await fetch_and_store_rates("USD", [], date(2026, 1, 15), mock_session)
        mock_session.execute.assert_not_called()

    async def test_all_targets_match_base(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        with respx.mock(assert_all_mocked=True):
            await fetch_and_store_rates("USD", ["USD", "usd"], date(2026, 1, 15), mock_session)
        mock_session.execute.assert_not_called()


# ===========================================================================
# Integration tests -- require real Postgres
# ===========================================================================


@pytest.mark.integration
async def test_get_rate_exact_db_hit(session: AsyncSession) -> None:
    """get_rate returns stored rate without HTTP when exact date row exists."""
    rate_date = date(2026, 1, 15)
    stored_rate = Decimal("1.08500000")

    await _upsert_rate(session, "EUR", "USD", rate_date, stored_rate, "frankfurter")
    await session.flush()

    # Any HTTP call would raise since no routes registered
    with respx.mock(assert_all_mocked=True):
        rate, is_approx = await get_rate("EUR", "USD", rate_date, session)

    assert rate == stored_rate
    assert is_approx is False


@pytest.mark.integration
async def test_get_rate_miss_fetches_from_frankfurter_and_stores(session: AsyncSession) -> None:
    """get_rate fetches rate on DB miss, stores it, returns (rate, False)."""
    rate_date = date(2026, 1, 16)
    expected_rate = Decimal("1.08420000")

    with respx.mock() as mock:
        mock.get(f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}").mock(
            return_value=Response(
                200,
                json={
                    "amount": 1,
                    "base": "EUR",
                    "date": str(rate_date),
                    "rates": {"USD": float(expected_rate)},
                },
            )
        )
        rate, is_approx = await get_rate("EUR", "USD", rate_date, session)

    assert rate == expected_rate
    assert is_approx is False

    stored = await _db_exact(session, "EUR", "USD", rate_date)
    assert stored is not None
    assert stored.source == "frankfurter"


@pytest.mark.integration
async def test_get_rate_frankfurter_down_falls_back_to_nearest_prior(session: AsyncSession) -> None:
    """Frankfurter failure uses nearest prior DB rate, is_approximate=True."""
    target_date = date(2026, 1, 20)
    prior_date = date(2026, 1, 10)
    fallback_rate = Decimal("1.07500000")

    await _upsert_rate(session, "EUR", "USD", prior_date, fallback_rate, "frankfurter")
    await session.flush()

    with respx.mock() as mock:
        # 500 causes raise_for_status() to raise -> caught -> returns None
        mock.get(f"{_FRANKFURTER_BASE}/{target_date.isoformat()}").mock(return_value=Response(500))
        rate, is_approx = await get_rate("EUR", "USD", target_date, session)

    assert rate == fallback_rate
    assert is_approx is True


@pytest.mark.integration
async def test_get_rate_nothing_available_raises(session: AsyncSession) -> None:
    """No DB rate and Frankfurter 404 raises FXRateUnavailableError."""
    rate_date = date(2026, 3, 15)

    with respx.mock() as mock:
        mock.get(f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}").mock(return_value=Response(404))
        with pytest.raises(FXRateUnavailableError):
            await get_rate("JPY", "CHF", rate_date, session)


@pytest.mark.integration
async def test_fetch_and_store_rates_idempotent(session: AsyncSession) -> None:
    """Calling fetch_and_store_rates twice produces exactly one row per pair."""
    rate_date = date(2026, 1, 17)

    with respx.mock() as mock:
        mock.get(f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}").mock(
            return_value=Response(
                200,
                json={
                    "amount": 1,
                    "base": "EUR",
                    "date": str(rate_date),
                    "rates": {"USD": 1.0842, "GBP": 0.8543},
                },
            )
        )
        await fetch_and_store_rates("EUR", ["USD", "GBP"], rate_date, session)
        await fetch_and_store_rates("EUR", ["USD", "GBP"], rate_date, session)

    count_result = await session.execute(
        sa.select(sa.func.count())
        .select_from(FxRate)
        .where(
            FxRate.rate_date == rate_date,
            FxRate.from_currency == "EUR",
            FxRate.to_currency == "USD",
        )
    )
    assert count_result.scalar() == 1


@pytest.mark.integration
async def test_fetch_and_store_rates_http_failure_does_not_raise(session: AsyncSession) -> None:
    """HTTP failure is swallowed; no rows written."""
    rate_date = date(2026, 2, 1)

    with respx.mock() as mock:
        mock.get(f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}").mock(return_value=Response(503))
        await fetch_and_store_rates("EUR", ["USD"], rate_date, session)

    count_result = await session.execute(
        sa.select(sa.func.count()).select_from(FxRate).where(FxRate.rate_date == rate_date)
    )
    assert count_result.scalar() == 0


@pytest.mark.integration
async def test_convert_rounds_to_four_decimal_places(session: AsyncSession) -> None:
    """convert() applies ROUND_HALF_UP to 4 decimal places."""
    rate_date = date(2026, 1, 18)
    raw_rate = Decimal("1.123456789")
    await _upsert_rate(session, "EUR", "USD", rate_date, raw_rate, "frankfurter")
    await session.flush()

    amount = Decimal("1.00")
    result, is_approx = await convert(amount, "EUR", "USD", rate_date, session)

    expected = (amount * raw_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert result == expected
    assert is_approx is False


@pytest.mark.integration
async def test_home_currency_transaction_no_fx_fields(session: AsyncSession) -> None:
    """Transaction where account currency == household home currency gets no FX data."""
    actor_id, household_id, account_id = await _make_household_and_account(
        session, home_currency="USD", account_currency="USD"
    )
    tx = await tx_service.create_transaction(
        session,
        **_tx_kwargs(household_id, account_id, actor_id, currency="USD", home_currency="USD"),
    )
    assert tx.fx_rate_source == "none"
    assert tx.home_currency_amount is None
    assert tx.fx_rate is None


@pytest.mark.integration
async def test_foreign_currency_transaction_gets_auto_rate(session: AsyncSession) -> None:
    """Foreign-currency transaction auto-fetches and stores FX rate on create."""
    rate_date = date(2026, 1, 15)
    eur_usd_rate = Decimal("1.08420000")
    actor_id, household_id, account_id = await _make_household_and_account(
        session, home_currency="USD", account_currency="EUR"
    )
    await _upsert_rate(session, "EUR", "USD", rate_date, eur_usd_rate, "frankfurter")
    await session.flush()

    with respx.mock(assert_all_mocked=True):
        tx = await tx_service.create_transaction(
            session,
            **_tx_kwargs(
                household_id,
                account_id,
                actor_id,
                currency="EUR",
                home_currency="USD",
                occurred_at=rate_date,
                amount=Decimal("100.00"),
            ),
        )

    assert tx.fx_rate_source == "frankfurter"
    assert tx.home_currency == "USD"
    expected_home = (Decimal("100.00") * eur_usd_rate).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    assert tx.home_currency_amount == expected_home


@pytest.mark.integration
async def test_manual_override_source_not_overwritten_by_daily_fetch(session: AsyncSession) -> None:
    """update_transaction_fx_rate sets source=manual; fetch_and_store_rates does not reset it."""
    rate_date = date(2026, 1, 15)
    actor_id, household_id, account_id = await _make_household_and_account(
        session, home_currency="USD", account_currency="EUR"
    )
    await _upsert_rate(session, "EUR", "USD", rate_date, Decimal("1.08420000"), "frankfurter")
    await session.flush()

    with respx.mock(assert_all_mocked=True):
        tx = await tx_service.create_transaction(
            session,
            **_tx_kwargs(
                household_id,
                account_id,
                actor_id,
                currency="EUR",
                home_currency="USD",
                occurred_at=rate_date,
            ),
        )

    assert tx.fx_rate_source == "frankfurter"

    tx = await tx_service.update_transaction_fx_rate(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        rate=Decimal("1.1000"),
        note="manual override",
    )
    assert tx.fx_rate_source == "manual"
    assert tx.fx_rate == Decimal("1.1000")

    # Simulate daily rates job -- updates platform_fx_rate only
    with respx.mock() as mock:
        mock.get(f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}").mock(
            return_value=Response(
                200,
                json={
                    "amount": 1,
                    "base": "EUR",
                    "date": str(rate_date),
                    "rates": {"USD": 1.0900},
                },
            )
        )
        await fetch_and_store_rates("EUR", ["USD"], rate_date, session)

    await session.refresh(tx)
    # Transaction source must remain manual
    assert tx.fx_rate_source == "manual"
    assert tx.fx_rate == Decimal("1.1000")


# ===========================================================================
# Hypothesis property tests
# ===========================================================================

_pos_money = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_rate_near_one = st.decimals(
    min_value=Decimal("0.5000"),
    max_value=Decimal("2.0000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@given(amount=_pos_money, rate=_rate_near_one)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_convert_roundtrip_within_rounding_tolerance(
    amount: Decimal, rate: Decimal
) -> None:
    """Forward A->B then inverse B->A stays within 1 cent for rates in [0.5, 2.0].

    Tests the quantize(ROUND_HALF_UP) formula used inside convert().
    With exact inverse rate and 4dp rounding, the maximum round-trip error is
    ~2 * 0.00005 * max_rate = 0.0002 << 0.01.
    """
    b = (amount * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    inv = Decimal("1") / rate
    a_back = (b * inv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert abs(a_back - amount) <= Decimal("0.01")


_rate_wide = st.decimals(
    min_value=Decimal("0.0100"),
    max_value=Decimal("150.0000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@given(amount=_pos_money, rate=_rate_wide)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_hypothesis_convert_roundtrip_wide_rate_range(amount: Decimal, rate: Decimal) -> None:
    """Round-trip tolerance for rates in [0.01, 150] (covers JPY-class pairs).

    For rate r, a 4dp rounding error epsilon in the forward direction amplifies
    to epsilon/r in the inverse direction.  Tolerance = max($0.01, 2*eps/rate)
    where eps = 0.00005.
    """
    b = (amount * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    inv = Decimal("1") / rate
    a_back = (b * inv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    # Propagated rounding tolerance: forward error (0.00005) * 1/rate, rounded up
    eps = Decimal("0.00005")
    tolerance = max(Decimal("0.01"), (eps / rate + eps).quantize(Decimal("0.01"), ROUND_HALF_UP))
    assert abs(a_back - amount) <= tolerance, (
        f"Round-trip error {abs(a_back - amount)} > tolerance {tolerance} "
        f"for amount={amount}, rate={rate}"
    )


@pytest.mark.integration
async def test_convert_is_approximate_propagates_from_fallback(session: AsyncSession) -> None:
    """convert() returns is_approximate=True when get_rate() uses a fallback rate.

    This validates the propagation path: get_rate -> is_approx -> convert return value.
    """
    target_date = date(2026, 4, 20)
    prior_date = date(2026, 4, 10)
    fallback_rate = Decimal("1.08500000")

    await _upsert_rate(session, "EUR", "USD", prior_date, fallback_rate, "frankfurter")
    await session.flush()

    with respx.mock() as mock:
        # API failure forces fallback to prior rate
        mock.get(f"{_FRANKFURTER_BASE}/{target_date.isoformat()}").mock(return_value=Response(503))
        converted, is_approx = await convert(Decimal("100.00"), "EUR", "USD", target_date, session)

    expected = (Decimal("100.00") * fallback_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    assert converted == expected
    assert is_approx is True


@pytest.mark.integration
async def test_convert_same_currency_never_approximate(session: AsyncSession) -> None:
    """convert(amount, X, X, ...) always returns (amount, False) — no DB hit, not approximate."""
    # No rates in DB, no HTTP mock — if DB is hit this will fail
    result_amount, is_approx = await convert(
        Decimal("500.00"), "GBP", "GBP", date(2026, 1, 1), session
    )
    assert result_amount == Decimal("500.00")
    assert is_approx is False
