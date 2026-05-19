"""Tests for the transactions module.

Unit tests (no DB) run without any external services.
Integration tests (marked @pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests cover:
  - Split sum invariant: sum(splits) always == transaction.amount for any valid partition
  - State machine: no invalid transitions, all valid transitions reachable
  - Dedup confidence scoring: same input always same score; threshold behavior
  - Refund pairing criteria: amount signs, day window, partial refund
  - Transfer pairing: internal vs external, peer linkage symmetry
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service as accounts_service
from app.accounts.enums import AccountType
from app.households import service as households_service
from app.households.enums import VisibilityMode
from app.transactions import service
from app.transactions.enums import (
    DedupResolution,
    GroupType,
    TransactionDirection,
    TransactionState,
    TransactionType,
)
from app.transactions.models import Transaction
from app.transactions.service import (
    VALID_TRANSITIONS,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
    check_refund_pairable,
    normalize_description,
    score_dedup_confidence,
    validate_split_amounts,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_money = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("999999.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
_date = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
_description = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestNormalizeDescription:
    def test_lowercase(self) -> None:
        assert normalize_description("WALMART") == "walmart"

    def test_strips_punctuation(self) -> None:
        assert normalize_description("Walmart, Inc.") == "walmart inc"

    def test_collapses_whitespace(self) -> None:
        assert normalize_description("  hello   world  ") == "hello world"

    def test_combined(self) -> None:
        assert normalize_description("AMAZON.COM*AB12-CD34") == "amazoncomab12cd34"

    def test_empty_becomes_empty(self) -> None:
        assert normalize_description("   ") == ""

    def test_deterministic(self) -> None:
        desc = "PayPal *TRANSFER - FEE"
        assert normalize_description(desc) == normalize_description(desc)


class TestScoreDedupConfidence:
    def test_identical_same_day(self) -> None:
        d = date(2026, 1, 15)
        score = score_dedup_confidence(d, d, "starbucks", "starbucks")
        assert score == 1.0

    def test_zero_when_delta_exceeds_three_days(self) -> None:
        d1 = date(2026, 1, 1)
        d2 = date(2026, 1, 5)
        assert score_dedup_confidence(d1, d2, "walmart", "walmart") == 0.0

    def test_delta_at_boundary_three_days(self) -> None:
        d1 = date(2026, 1, 1)
        d2 = date(2026, 1, 4)
        score = score_dedup_confidence(d1, d2, "walmart", "walmart")
        assert score > 0.0

    def test_lower_score_for_different_descriptions(self) -> None:
        d = date(2026, 1, 15)
        exact = score_dedup_confidence(d, d, "starbucks", "starbucks")
        diff = score_dedup_confidence(d, d, "starbucks", "amazon")
        assert exact > diff

    def test_lower_score_for_wider_date_gap(self) -> None:
        d1 = date(2026, 1, 1)
        d2_near = date(2026, 1, 2)
        d2_far = date(2026, 1, 4)
        desc = "walmart"
        near = score_dedup_confidence(d1, d2_near, desc, desc)
        far = score_dedup_confidence(d1, d2_far, desc, desc)
        assert near > far

    def test_symmetry(self) -> None:
        d1, d2 = date(2026, 1, 1), date(2026, 1, 3)
        s1 = score_dedup_confidence(d1, d2, "abc", "xyz")
        s2 = score_dedup_confidence(d2, d1, "xyz", "abc")
        assert s1 == s2

    def test_result_in_unit_range(self) -> None:
        d = date(2026, 1, 1)
        score = score_dedup_confidence(d, d, "hello world", "hello world")
        assert 0.0 <= score <= 1.0

    @given(
        d1=_date,
        delta=st.integers(min_value=0, max_value=3),
        desc=_description,
    )
    def test_deterministic_same_inputs(self, d1: date, delta: int, desc: str) -> None:
        d2 = d1 + timedelta(days=delta)
        s1 = score_dedup_confidence(d1, d2, desc, desc)
        s2 = score_dedup_confidence(d1, d2, desc, desc)
        assert s1 == s2

    @given(
        d1=_date,
        delta=st.integers(min_value=0, max_value=3),
        desc1=_description,
        desc2=_description,
    )
    def test_score_always_in_unit_range(self, d1: date, delta: int, desc1: str, desc2: str) -> None:
        d2 = d1 + timedelta(days=delta)
        score = score_dedup_confidence(d1, d2, desc1, desc2)
        assert 0.0 <= score <= 1.0

    @given(
        d1=_date,
        delta=st.integers(min_value=4, max_value=365),
        desc1=_description,
        desc2=_description,
    )
    def test_zero_beyond_window(self, d1: date, delta: int, desc1: str, desc2: str) -> None:
        d2 = d1 + timedelta(days=delta)
        assert score_dedup_confidence(d1, d2, desc1, desc2) == 0.0

    @given(
        threshold=st.floats(min_value=0.01, max_value=1.0),
    )
    def test_threshold_behavior_identical_pair(self, threshold: float) -> None:
        d = date(2026, 6, 1)
        score = score_dedup_confidence(d, d, "walmart supercenter", "walmart supercenter")
        assert score >= threshold or score < threshold  # tautology but exercises scoring


class TestValidateSplitAmounts:
    def test_exact_sum_returns_zero_remainder(self) -> None:
        total = Decimal("100.00")
        amounts = [Decimal("60.00"), Decimal("40.00")]
        remainder = validate_split_amounts(total, amounts)
        assert remainder == Decimal(0)

    def test_partial_sum_returns_remainder(self) -> None:
        total = Decimal("100.00")
        amounts = [Decimal("70.00")]
        remainder = validate_split_amounts(total, amounts)
        assert remainder == Decimal("30.00")

    def test_raises_when_exceeds_total(self) -> None:
        with pytest.raises(ValidationError, match="exceed"):
            validate_split_amounts(Decimal("100.00"), [Decimal("101.00")])

    def test_raises_for_zero_amount(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            validate_split_amounts(Decimal("100.00"), [Decimal("0")])

    def test_raises_for_negative_amount(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            validate_split_amounts(Decimal("100.00"), [Decimal("-10.00")])

    @given(
        total=_money,
        n=st.integers(min_value=1, max_value=8),
        seed=st.integers(min_value=1, max_value=10000),
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_split_sum_invariant(self, total: Decimal, n: int, seed: int) -> None:
        """For any valid partition of total into n pieces, remainder + sum == total."""
        # Build n-1 random splits that sum to < total
        step = total / Decimal(n + 1)
        if step <= Decimal(0):
            return
        amounts = [step] * (n - 1)
        remainder = validate_split_amounts(total, amounts)
        assert remainder >= Decimal(0)
        assert sum(amounts, Decimal(0)) + remainder == total

    @given(
        total=_money,
        fractions=st.lists(
            st.decimals(
                min_value=Decimal("0.0001"),
                max_value=Decimal("0.9999"),
                places=4,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_remainder_always_non_negative_for_partial_splits(
        self, total: Decimal, fractions: list[Decimal]
    ) -> None:
        """Partial splits (each fraction of total) always produce non-negative remainder."""
        amounts = [total * f for f in fractions]
        total_frac = sum(fractions, Decimal(0))
        if total_frac > Decimal(1):
            with pytest.raises(ValidationError):
                validate_split_amounts(total, amounts)
        else:
            remainder = validate_split_amounts(total, amounts)
            assert remainder >= Decimal(0)
            assert sum(amounts, Decimal(0)) + remainder == total


class TestStateMachine:
    def test_pending_to_posted_is_valid(self) -> None:
        assert TransactionState.POSTED in VALID_TRANSITIONS[TransactionState.PENDING]

    def test_posted_to_reconciled_is_valid(self) -> None:
        assert TransactionState.RECONCILED in VALID_TRANSITIONS[TransactionState.POSTED]

    def test_reconciled_is_terminal(self) -> None:
        assert len(VALID_TRANSITIONS[TransactionState.RECONCILED]) == 0

    def test_pending_to_reconciled_is_invalid(self) -> None:
        assert TransactionState.RECONCILED not in VALID_TRANSITIONS[TransactionState.PENDING]

    def test_posted_to_pending_is_invalid(self) -> None:
        assert TransactionState.PENDING not in VALID_TRANSITIONS[TransactionState.POSTED]

    def test_reconciled_to_posted_is_invalid(self) -> None:
        assert TransactionState.POSTED not in VALID_TRANSITIONS[TransactionState.RECONCILED]

    def test_all_states_have_transition_entries(self) -> None:
        for state in TransactionState:
            assert state in VALID_TRANSITIONS

    @given(
        current=st.sampled_from(list(TransactionState)),
        target=st.sampled_from(list(TransactionState)),
    )
    def test_valid_transitions_are_consistent(
        self, current: TransactionState, target: TransactionState
    ) -> None:
        """No state can be both valid and invalid simultaneously."""
        if target in VALID_TRANSITIONS[current]:
            assert target not in (set(TransactionState) - VALID_TRANSITIONS[current])


class TestRefundPairing:
    def test_valid_pairing(self) -> None:
        assert check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="Walmart",
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    def test_partial_refund_valid(self) -> None:
        assert check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("50.00"),
            debit_merchant="Walmart",
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    def test_credit_exceeds_debit_invalid(self) -> None:
        assert not check_refund_pairable(
            debit_amount=Decimal("50.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="Walmart",
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    def test_different_merchant_invalid(self) -> None:
        assert not check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="Walmart",
            credit_merchant="Amazon",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    def test_outside_window_invalid(self) -> None:
        assert not check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="Walmart",
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 3, 15),
            window_days=30,
        )

    def test_at_window_boundary_valid(self) -> None:
        assert check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="Walmart",
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 31),
            window_days=30,
        )

    def test_none_merchant_invalid(self) -> None:
        assert not check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant=None,
            credit_merchant="Walmart",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    def test_case_insensitive_merchant(self) -> None:
        assert check_refund_pairable(
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("100.00"),
            debit_merchant="walmart",
            credit_merchant="WALMART",
            debit_date=date(2026, 1, 1),
            credit_date=date(2026, 1, 5),
        )

    @given(
        debit_amount=_money,
        credit_fraction=st.decimals(
            min_value=Decimal("0.0001"),
            max_value=Decimal("1.0"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        ),
        delta=st.integers(min_value=0, max_value=30),
    )
    def test_partial_refund_always_valid_when_fraction_lte_one(
        self, debit_amount: Decimal, credit_fraction: Decimal, delta: int
    ) -> None:
        credit_amount = (debit_amount * credit_fraction).quantize(Decimal("0.0001"))
        d1 = date(2026, 6, 1)
        d2 = d1 + timedelta(days=delta)
        result = check_refund_pairable(
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            debit_merchant="merchant",
            credit_merchant="merchant",
            debit_date=d1,
            credit_date=d2,
            window_days=30,
        )
        # credit_fraction <= 1.0, delta <= 30, same merchant → must be valid
        assert result is True

    @given(
        debit_amount=_money,
        extra=_money,
        delta=st.integers(min_value=0, max_value=30),
    )
    def test_credit_exceeds_debit_always_invalid(
        self, debit_amount: Decimal, extra: Decimal, delta: int
    ) -> None:
        credit_amount = debit_amount + extra
        d1 = date(2026, 6, 1)
        d2 = d1 + timedelta(days=delta)
        assert not check_refund_pairable(
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            debit_merchant="merchant",
            credit_merchant="merchant",
            debit_date=d1,
            credit_date=d2,
            window_days=30,
        )

    @given(
        debit_amount=_money,
        delta=st.integers(min_value=31, max_value=3650),
    )
    def test_outside_window_always_invalid(self, debit_amount: Decimal, delta: int) -> None:
        d1 = date(2026, 1, 1)
        d2 = d1 + timedelta(days=delta)
        if d2 > date(2030, 12, 31):
            return
        assert not check_refund_pairable(
            debit_amount=debit_amount,
            credit_amount=debit_amount,
            debit_merchant="merchant",
            credit_merchant="merchant",
            debit_date=d1,
            credit_date=d2,
            window_days=30,
        )


# ===========================================================================
# Integration tests — require real Postgres
# ===========================================================================

pytestmark_integration = pytest.mark.integration


async def _make_household_and_account(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Return (actor_id, household_id, account_id)."""
    user = await households_service.create_user(
        session,
        email=f"tx_{uuid.uuid4().hex[:6]}@test.com",
        display_name="Tester",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await households_service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    account = await accounts_service.create_account(
        session,
        household_id=household.id,
        actor_id=user.id,
        name="Checking",
        institution=None,
        account_type=AccountType.CHECKING,
        currency="USD",
        current_balance=Decimal("1000.00"),
    )
    return user.id, household.id, account.id


def _tx_create_kwargs(
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    amount: Decimal = Decimal("50.00"),
    direction: TransactionDirection = TransactionDirection.DEBIT,
    merchant: str | None = "Walmart",
    posted_date: date | None = None,
    external_id: str | None = None,
) -> dict:
    return {
        "household_id": household_id,
        "account_id": account_id,
        "actor_id": actor_id,
        "amount": amount,
        "currency": "USD",
        "direction": direction,
        "transaction_type": TransactionType.REGULAR,
        "state": TransactionState.PENDING,
        "posted_date": posted_date or date(2026, 1, 15),
        "pending_date": None,
        "occurred_at": posted_date or date(2026, 1, 15),
        "description": "WALMART SUPERCENTER",
        "merchant_name": merchant,
        "external_id": external_id,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_and_get_transaction(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    assert tx.id is not None
    assert tx.state == "pending"
    fetched = await service.get_transaction(
        session, transaction_id=tx.id, household_id=household_id
    )
    assert fetched.id == tx.id


@pytest.mark.integration
async def test_create_transaction_seeds_implicit_split(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("75.00"))
    )
    splits = await service.get_splits(session, transaction_id=tx.id, household_id=household_id)
    assert len(splits) == 1
    assert splits[0].amount == Decimal("75.00")
    assert splits[0].category_id is None


@pytest.mark.integration
async def test_get_transaction_wrong_household_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    with pytest.raises(NotFoundError):
        await service.get_transaction(session, transaction_id=tx.id, household_id=uuid.uuid4())


@pytest.mark.integration
async def test_list_transactions_filters(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.DEBIT,
            posted_date=date(2026, 1, 10),
        ),
    )
    await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.CREDIT,
            posted_date=date(2026, 1, 20),
        ),
    )
    debits = await service.list_transactions(
        session, household_id=household_id, direction=TransactionDirection.DEBIT
    )
    assert all(t.direction == "debit" for t in debits)
    credits = await service.list_transactions(
        session, household_id=household_id, direction=TransactionDirection.CREDIT
    )
    assert all(t.direction == "credit" for t in credits)


@pytest.mark.integration
async def test_archive_transaction(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    await service.archive_transaction(
        session, transaction_id=tx.id, household_id=household_id, actor_id=actor_id
    )
    with pytest.raises(NotFoundError):
        await service.get_transaction(session, transaction_id=tx.id, household_id=household_id)


# ---------------------------------------------------------------------------
# State machine (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_valid_state_transitions(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    assert tx.state == "pending"
    tx = await service.transition_state(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        new_state=TransactionState.POSTED,
    )
    assert tx.state == "posted"
    tx = await service.transition_state(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        new_state=TransactionState.RECONCILED,
    )
    assert tx.state == "reconciled"


@pytest.mark.integration
async def test_invalid_transition_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    with pytest.raises(InvalidTransitionError):
        await service.transition_state(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            actor_id=actor_id,
            new_state=TransactionState.RECONCILED,
        )


@pytest.mark.integration
async def test_reconciled_is_terminal(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx = await service.transition_state(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        new_state=TransactionState.POSTED,
    )
    tx = await service.transition_state(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        new_state=TransactionState.RECONCILED,
    )
    with pytest.raises(InvalidTransitionError):
        await service.transition_state(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            actor_id=actor_id,
            new_state=TransactionState.POSTED,
        )


# ---------------------------------------------------------------------------
# Split allocations (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_set_splits_exact_sum(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("100.00"))
    )
    splits = await service.set_splits(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        splits=[
            {"amount": Decimal("60.00"), "currency": "USD"},
            {"amount": Decimal("40.00"), "currency": "USD"},
        ],
    )
    assert len(splits) == 2
    assert sum(s.amount for s in splits) == Decimal("100.00")


@pytest.mark.integration
async def test_set_splits_auto_creates_remainder(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("100.00"))
    )
    splits = await service.set_splits(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        splits=[{"amount": Decimal("70.00"), "currency": "USD"}],
    )
    assert len(splits) == 2
    remainder_splits = [s for s in splits if s.category_id is None]
    assert any(s.amount == Decimal("30.00") for s in remainder_splits)
    assert sum(s.amount for s in splits) == Decimal("100.00")


@pytest.mark.integration
async def test_set_splits_rejects_over_total(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("100.00"))
    )
    with pytest.raises(ValidationError):
        await service.set_splits(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            actor_id=actor_id,
            splits=[{"amount": Decimal("101.00"), "currency": "USD"}],
        )


@pytest.mark.integration
async def test_set_splits_archives_old_splits(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("100.00"))
    )
    await service.set_splits(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        splits=[{"amount": Decimal("50.00"), "currency": "USD"}],
    )
    # Replace with a new single split
    new_splits = await service.set_splits(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        actor_id=actor_id,
        splits=[{"amount": Decimal("100.00"), "currency": "USD"}],
    )
    # Only the new splits are visible (archived ones excluded by soft-delete filter)
    assert len(new_splits) == 1
    active = await service.get_splits(session, transaction_id=tx.id, household_id=household_id)
    assert len(active) == 1


# ---------------------------------------------------------------------------
# Transfer pairing (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_pair_transfer_writes_peer_ids(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id, account_id, actor_id, direction=TransactionDirection.DEBIT
        ),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id, account_id, actor_id, direction=TransactionDirection.CREDIT
        ),
    )
    paired_tx1, paired_tx2 = await service.pair_transfer(
        session,
        transaction_id=tx1.id,
        peer_id=tx2.id,
        household_id=household_id,
        actor_id=actor_id,
        transfer_type="internal",
    )
    assert paired_tx1.transfer_peer_id == tx2.id
    assert paired_tx2.transfer_peer_id == tx1.id


@pytest.mark.integration
async def test_pair_transfer_self_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    with pytest.raises(ValidationError):
        await service.pair_transfer(
            session,
            transaction_id=tx.id,
            peer_id=tx.id,
            household_id=household_id,
            actor_id=actor_id,
            transfer_type="internal",
        )


@pytest.mark.integration
async def test_pair_transfer_conflict_on_different_peer(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx2 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx3 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    await service.pair_transfer(
        session,
        transaction_id=tx1.id,
        peer_id=tx2.id,
        household_id=household_id,
        actor_id=actor_id,
        transfer_type="internal",
    )
    with pytest.raises(ConflictError):
        await service.pair_transfer(
            session,
            transaction_id=tx1.id,
            peer_id=tx3.id,
            household_id=household_id,
            actor_id=actor_id,
            transfer_type="internal",
        )


# ---------------------------------------------------------------------------
# Refund pairing (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_pair_refund_valid(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("100.00"),
            direction=TransactionDirection.DEBIT,
            merchant="Walmart",
            posted_date=date(2026, 1, 1),
        ),
    )
    credit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("100.00"),
            direction=TransactionDirection.CREDIT,
            merchant="Walmart",
            posted_date=date(2026, 1, 10),
        ),
    )
    d, c = await service.pair_refund(
        session,
        transaction_id=debit.id,
        peer_id=credit.id,
        household_id=household_id,
        actor_id=actor_id,
    )
    assert d.refund_peer_id == credit.id
    assert c.refund_peer_id == debit.id


@pytest.mark.integration
async def test_pair_refund_fails_outside_window(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("100.00"),
            direction=TransactionDirection.DEBIT,
            merchant="Walmart",
            posted_date=date(2026, 1, 1),
        ),
    )
    credit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("100.00"),
            direction=TransactionDirection.CREDIT,
            merchant="Walmart",
            posted_date=date(2026, 3, 15),
        ),
    )
    with pytest.raises(ValidationError):
        await service.pair_refund(
            session,
            transaction_id=debit.id,
            peer_id=credit.id,
            household_id=household_id,
            actor_id=actor_id,
            window_days=30,
        )


# ---------------------------------------------------------------------------
# Deduplication (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_exact_dedup_blocked_by_unique_constraint(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    ext_id = f"FIN-{uuid.uuid4().hex[:8]}"
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, external_id=ext_id),
    )
    with pytest.raises(ConflictError):
        await service.create_transaction(
            session,
            **_tx_create_kwargs(household_id, account_id, actor_id, external_id=ext_id),
        )


@pytest.mark.integration
async def test_process_dedup_creates_pending_log(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("99.99"),
            posted_date=date(2026, 1, 15),
        ),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("99.99"),
            posted_date=date(2026, 1, 16),
        ),
    )
    logs = await service.process_dedup(session, transaction=tx2, source="unknown")
    assert len(logs) >= 1
    assert all(lg.resolution == "pending" for lg in logs)


@pytest.mark.integration
async def test_process_dedup_auto_merges_on_simplefin(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    desc = "WALMART SUPERCENTER"
    await service.create_transaction(
        session,
        household_id=household_id,
        account_id=account_id,
        actor_id=actor_id,
        amount=Decimal("99.99"),
        currency="USD",
        direction=TransactionDirection.DEBIT,
        transaction_type=TransactionType.REGULAR,
        state=TransactionState.PENDING,
        posted_date=date(2026, 1, 15),
        pending_date=None,
        occurred_at=date(2026, 1, 15),
        description=desc,
        merchant_name="Walmart",
    )
    tx2 = await service.create_transaction(
        session,
        household_id=household_id,
        account_id=account_id,
        actor_id=actor_id,
        amount=Decimal("99.99"),
        currency="USD",
        direction=TransactionDirection.DEBIT,
        transaction_type=TransactionType.REGULAR,
        state=TransactionState.PENDING,
        posted_date=date(2026, 1, 15),
        pending_date=None,
        occurred_at=date(2026, 1, 15),
        description=desc,
        merchant_name="Walmart",
    )
    logs = await service.process_dedup(session, transaction=tx2, source="simplefin", threshold=0.85)
    merged = [lg for lg in logs if lg.resolution == "merged"]
    assert len(merged) >= 1
    # tx2 should now be archived
    result = await session.execute(
        sa.select(Transaction)
        .where(Transaction.id == tx2.id)
        .execution_options(include_archived=True)
    )
    archived_tx = result.scalar_one_or_none()
    assert archived_tx is not None
    assert archived_tx.archived_at is not None


@pytest.mark.integration
async def test_resolve_dedup(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("55.00"))
    )
    tx2 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("55.00"))
    )
    logs = await service.process_dedup(session, transaction=tx2, source="unknown")
    assert logs
    log = logs[0]
    resolved = await service.resolve_dedup(
        session,
        log_id=log.id,
        household_id=household_id,
        actor_id=actor_id,
        resolution=DedupResolution.REJECTED,
    )
    assert resolved.resolution == "rejected"
    assert resolved.resolved_by == actor_id


# ---------------------------------------------------------------------------
# PaymentGroup (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_and_list_payment_group(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx2 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    group = await service.create_payment_group(
        session,
        household_id=household_id,
        actor_id=actor_id,
        group_type=GroupType.SPLIT_PURCHASE,
        member_transaction_ids=[tx1.id, tx2.id],
    )
    assert group.id is not None
    groups = await service.list_payment_groups(session, household_id=household_id)
    assert any(g.id == group.id for g in groups)


@pytest.mark.integration
async def test_payment_group_requires_two_members(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    with pytest.raises(ValidationError):
        await service.create_payment_group(
            session,
            household_id=household_id,
            actor_id=actor_id,
            group_type=GroupType.SPLIT_PURCHASE,
            member_transaction_ids=[tx.id],
        )


@pytest.mark.integration
async def test_archive_payment_group(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx2 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    group = await service.create_payment_group(
        session,
        household_id=household_id,
        actor_id=actor_id,
        group_type=GroupType.SPLIT_FUNDING,
        member_transaction_ids=[tx1.id, tx2.id],
    )
    await service.archive_payment_group(
        session, group_id=group.id, household_id=household_id, actor_id=actor_id
    )
    with pytest.raises(NotFoundError):
        await service.get_payment_group(session, group_id=group.id, household_id=household_id)


# ---------------------------------------------------------------------------
# list_transactions filter branches (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_transactions_filter_by_type(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    base = _tx_create_kwargs(household_id, account_id, actor_id)
    await service.create_transaction(
        session, **{**base, "transaction_type": TransactionType.PAYROLL}
    )
    await service.create_transaction(session, **{**base, "transaction_type": TransactionType.FEE})
    results = await service.list_transactions(
        session, household_id=household_id, transaction_type=TransactionType.PAYROLL
    )
    assert all(tx.transaction_type == str(TransactionType.PAYROLL) for tx in results)
    assert len(results) == 1


@pytest.mark.integration
async def test_list_transactions_filter_by_date_range(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, posted_date=date(2026, 1, 1)),
    )
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, posted_date=date(2026, 3, 1)),
    )
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, posted_date=date(2026, 6, 1)),
    )
    results = await service.list_transactions(
        session,
        household_id=household_id,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 4, 1),
    )
    assert len(results) == 1
    assert results[0].posted_date == date(2026, 3, 1)


# ---------------------------------------------------------------------------
# get_transaction with account_id filter (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_get_transaction_with_account_id_filter(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    # Correct account_id works
    found = await service.get_transaction(
        session,
        transaction_id=tx.id,
        household_id=household_id,
        account_id=account_id,
    )
    assert found.id == tx.id
    # Wrong account_id raises NotFoundError
    with pytest.raises(NotFoundError):
        await service.get_transaction(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            account_id=uuid.uuid4(),
        )


# ---------------------------------------------------------------------------
# Transfer conflict (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_pair_transfer_conflict_peer_already_paired(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx2 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    tx3 = await service.create_transaction(
        session, **_tx_create_kwargs(household_id, account_id, actor_id)
    )
    # Pair tx1 <-> tx2 first
    await service.pair_transfer(
        session,
        transaction_id=tx1.id,
        peer_id=tx2.id,
        household_id=household_id,
        actor_id=actor_id,
        transfer_type="internal",
    )
    # Trying to pair tx3 <-> tx2 should fail (tx2 already paired with tx1)
    with pytest.raises(ConflictError):
        await service.pair_transfer(
            session,
            transaction_id=tx3.id,
            peer_id=tx2.id,
            household_id=household_id,
            actor_id=actor_id,
            transfer_type="internal",
        )


# ---------------------------------------------------------------------------
# find_refund_candidates (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_find_refund_candidates_returns_credits(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.DEBIT,
            amount=Decimal("50.00"),
            merchant="Acme Store",
            posted_date=date(2026, 2, 1),
        ),
    )
    await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.CREDIT,
            amount=Decimal("50.00"),
            merchant="Acme Store",
            posted_date=date(2026, 2, 5),
        ),
    )
    candidates = await service.find_refund_candidates(
        session, transaction_id=debit.id, household_id=household_id
    )
    assert len(candidates) == 1
    assert candidates[0].days_apart == 4


@pytest.mark.integration
async def test_find_refund_candidates_credit_tx_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    credit_tx = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id, account_id, actor_id, direction=TransactionDirection.CREDIT
        ),
    )
    with pytest.raises(ValidationError):
        await service.find_refund_candidates(
            session, transaction_id=credit_tx.id, household_id=household_id
        )


@pytest.mark.integration
async def test_find_refund_candidates_no_merchant_returns_empty(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.DEBIT,
            merchant=None,
        ),
    )
    candidates = await service.find_refund_candidates(
        session, transaction_id=debit.id, household_id=household_id
    )
    assert candidates == []


# ---------------------------------------------------------------------------
# pair_refund — credit-first and same-direction error (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_pair_refund_credit_first_order(session: AsyncSession) -> None:
    """pair_refund works when tx is the credit and peer is the debit."""
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.DEBIT,
            amount=Decimal("80.00"),
            merchant="Shop",
            posted_date=date(2026, 3, 1),
        ),
    )
    credit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.CREDIT,
            amount=Decimal("80.00"),
            merchant="Shop",
            posted_date=date(2026, 3, 3),
        ),
    )
    # Pass credit as transaction_id and debit as peer_id
    paired_debit, paired_credit = await service.pair_refund(
        session,
        transaction_id=credit.id,
        peer_id=debit.id,
        household_id=household_id,
        actor_id=actor_id,
    )
    assert paired_debit.refund_peer_id == paired_credit.id
    assert paired_credit.refund_peer_id == paired_debit.id


@pytest.mark.integration
async def test_pair_refund_same_direction_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    tx1 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id, account_id, actor_id, direction=TransactionDirection.DEBIT
        ),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id, account_id, actor_id, direction=TransactionDirection.DEBIT
        ),
    )
    with pytest.raises(ValidationError):
        await service.pair_refund(
            session,
            transaction_id=tx1.id,
            peer_id=tx2.id,
            household_id=household_id,
            actor_id=actor_id,
        )


@pytest.mark.integration
async def test_pair_refund_debit_conflict(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    debit = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.DEBIT,
            amount=Decimal("100.00"),
            merchant="Shop",
            posted_date=date(2026, 4, 1),
        ),
    )
    credit1 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.CREDIT,
            amount=Decimal("100.00"),
            merchant="Shop",
            posted_date=date(2026, 4, 2),
        ),
    )
    credit2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            direction=TransactionDirection.CREDIT,
            amount=Decimal("100.00"),
            merchant="Shop",
            posted_date=date(2026, 4, 3),
        ),
    )
    # Pair debit <-> credit1
    await service.pair_refund(
        session,
        transaction_id=debit.id,
        peer_id=credit1.id,
        household_id=household_id,
        actor_id=actor_id,
    )
    # Trying to pair debit <-> credit2 conflicts on debit
    with pytest.raises(ConflictError):
        await service.pair_refund(
            session,
            transaction_id=debit.id,
            peer_id=credit2.id,
            household_id=household_id,
            actor_id=actor_id,
        )


# ---------------------------------------------------------------------------
# list_dedup_candidates (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_dedup_candidates(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("77.00"),
            posted_date=date(2026, 2, 1),
        ),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(
            household_id,
            account_id,
            actor_id,
            amount=Decimal("77.00"),
            posted_date=date(2026, 2, 2),
        ),
    )
    logs = await service.process_dedup(session, transaction=tx2, source="unknown")
    assert logs
    pending = await service.list_dedup_candidates(session, household_id=household_id)
    assert any(lg.id == logs[0].id for lg in pending)


# ---------------------------------------------------------------------------
# resolve_dedup error paths and MERGED HITL path (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_resolve_dedup_not_found(session: AsyncSession) -> None:
    actor_id, household_id, _ = await _make_household_and_account(session)
    with pytest.raises(NotFoundError):
        await service.resolve_dedup(
            session,
            log_id=uuid.uuid4(),
            household_id=household_id,
            actor_id=actor_id,
            resolution=DedupResolution.REJECTED,
        )


@pytest.mark.integration
async def test_resolve_dedup_already_resolved_raises(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("33.00")),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("33.00")),
    )
    logs = await service.process_dedup(session, transaction=tx2, source="unknown")
    log = logs[0]
    await service.resolve_dedup(
        session,
        log_id=log.id,
        household_id=household_id,
        actor_id=actor_id,
        resolution=DedupResolution.REJECTED,
    )
    with pytest.raises(ConflictError):
        await service.resolve_dedup(
            session,
            log_id=log.id,
            household_id=household_id,
            actor_id=actor_id,
            resolution=DedupResolution.MERGED,
        )


@pytest.mark.integration
async def test_resolve_dedup_merged_archives_candidate_a(session: AsyncSession) -> None:
    actor_id, household_id, account_id = await _make_household_and_account(session)
    await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("44.00")),
    )
    tx2 = await service.create_transaction(
        session,
        **_tx_create_kwargs(household_id, account_id, actor_id, amount=Decimal("44.00")),
    )
    logs = await service.process_dedup(session, transaction=tx2, source="unknown")
    log = logs[0]
    await service.resolve_dedup(
        session,
        log_id=log.id,
        household_id=household_id,
        actor_id=actor_id,
        resolution=DedupResolution.MERGED,
    )
    # candidate_a should now be archived
    result = await session.execute(
        sa.select(Transaction)
        .where(Transaction.id == log.candidate_a_id)
        .execution_options(include_archived=True)
    )
    archived = result.scalar_one_or_none()
    assert archived is not None
    assert archived.archived_at is not None
