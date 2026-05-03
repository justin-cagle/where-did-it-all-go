"""Tests for the accounts module.

Unit tests run without any external services.
Integration tests (marked @pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests cover:
  - Balance update invariants (asset accounts never go negative without override)
  - AccountGroup candidate detection (same institution+balance+name always detected)
  - APR history effective-date ordering (no gaps, no overlaps after N updates)
  - Soft delete behavior (archived accounts excluded from default queries)
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.accounts import service
from app.accounts.enums import (
    ASSET_ACCOUNT_TYPES,
    LIABILITY_ACCOUNT_TYPES,
    AccountType,
    MinimumPaymentStrategy,
)
from app.accounts.models import Account, ManualAccount
from app.accounts.service import ValidationError, validate_balance
from app.database import Base
from app.households import service as households_service
from app.households.enums import VisibilityMode

pytestmark = pytest.mark.integration

_CHECKING = AccountType.CHECKING
_CREDIT = AccountType.CREDIT_CARD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def session(postgres_url: str) -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_user(session: AsyncSession, suffix: str = "") -> "households_service.User":  # type: ignore[name-defined]
    return await households_service.create_user(
        session,
        email=f"acct{suffix}_{uuid.uuid4().hex[:6]}@test.com",
        display_name="Tester",
        password="pw12345678",  # pragma: allowlist secret
    )


async def _make_household(
    session: AsyncSession,
    owner: "households_service.User",  # type: ignore[name-defined]
) -> "households_service.Household":  # type: ignore[name-defined]
    return await households_service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=owner,
    )


async def _make_account(
    session: AsyncSession,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    name: str = "Checking",
    institution: str | None = "First Bank",
    account_type: AccountType = AccountType.CHECKING,
    currency: str = "USD",
    current_balance: Decimal = Decimal("1000.00"),
) -> Account:
    return await service.create_account(
        session,
        household_id=household_id,
        actor_id=actor_id,
        name=name,
        institution=institution,
        account_type=account_type,
        currency=currency,
        current_balance=current_balance,
    )


# ---------------------------------------------------------------------------
# Unit tests — pure balance validation (no DB)
# ---------------------------------------------------------------------------


def test_validate_balance_asset_rejects_negative() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        validate_balance(AccountType.CHECKING, Decimal("-0.01"), allow_negative=False)


def test_validate_balance_asset_allows_negative_with_override() -> None:
    validate_balance(AccountType.CHECKING, Decimal("-100"), allow_negative=True)


def test_validate_balance_asset_allows_zero() -> None:
    validate_balance(AccountType.SAVINGS, Decimal("0"), allow_negative=False)


def test_validate_balance_liability_allows_negative() -> None:
    for acct_type in LIABILITY_ACCOUNT_TYPES:
        validate_balance(acct_type, Decimal("-500"), allow_negative=False)


def test_validate_balance_liability_allows_positive() -> None:
    validate_balance(AccountType.CREDIT_CARD, Decimal("50"), allow_negative=False)


# ---------------------------------------------------------------------------
# Hypothesis: balance invariant property
# ---------------------------------------------------------------------------


@given(
    balance=st.decimals(
        allow_nan=False,
        allow_infinity=False,
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
    ),
    account_type=st.sampled_from(list(AccountType)),
    allow_negative=st.booleans(),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_balance_invariant_property(
    balance: Decimal,
    account_type: AccountType,
    allow_negative: bool,
) -> None:
    """Asset accounts with negative balance always raise unless overridden."""
    is_asset = account_type in ASSET_ACCOUNT_TYPES
    should_raise = is_asset and balance < Decimal(0) and not allow_negative

    if should_raise:
        with pytest.raises(ValidationError):
            validate_balance(account_type, balance, allow_negative)
    else:
        validate_balance(account_type, balance, allow_negative)


# ---------------------------------------------------------------------------
# Integration: Account CRUD
# ---------------------------------------------------------------------------


async def test_create_account(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)

    assert account.id is not None
    assert account.household_id == hh.id
    assert account.name == "Checking"
    assert account.account_type == "checking"
    assert account.currency == "USD"
    assert account.current_balance == Decimal("1000.00")
    assert not account.is_manual


async def test_create_account_manual_type_sets_flag_and_creates_record(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(
        session, hh.id, user.id, account_type=AccountType.MANUAL, name="Cash"
    )

    assert account.is_manual
    manual_result = await session.execute(
        sa.select(ManualAccount).where(ManualAccount.account_id == account.id)
    )
    manual = manual_result.scalar_one_or_none()
    assert manual is not None
    assert manual.account_id == account.id


async def test_list_accounts_filter_by_type(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    await _make_account(session, hh.id, user.id, account_type=AccountType.CHECKING)
    await _make_account(session, hh.id, user.id, account_type=AccountType.SAVINGS, name="Savings")
    await _make_account(session, hh.id, user.id, account_type=AccountType.CREDIT_CARD, name="Visa")

    checking = await service.list_accounts(
        session, household_id=hh.id, account_type=AccountType.CHECKING
    )
    assert len(checking) == 1
    assert checking[0].account_type == "checking"


async def test_list_accounts_filter_by_manual(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    await _make_account(session, hh.id, user.id, account_type=AccountType.CHECKING)
    await _make_account(session, hh.id, user.id, account_type=AccountType.MANUAL, name="Cash")

    manual_only = await service.list_accounts(session, household_id=hh.id, is_manual=True)
    assert len(manual_only) == 1
    assert manual_only[0].name == "Cash"


async def test_get_account_household_scope(session: AsyncSession) -> None:
    """Account is invisible when queried with a different household_id."""
    user = await _make_user(session)
    hh1 = await _make_household(session, user)
    hh2 = await households_service.create_household(
        session,
        name="HH2",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    account = await _make_account(session, hh1.id, user.id)

    with pytest.raises(service.NotFoundError):
        await service.get_account(session, account_id=account.id, household_id=hh2.id)


async def test_update_account_name(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)

    updated = await service.update_account(
        session, account_id=account.id, household_id=hh.id, actor_id=user.id, name="Primary"
    )
    assert updated.name == "Primary"


async def test_update_account_balance_emits_audit(session: AsyncSession) -> None:
    from app.audit.models import AuditEvent

    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)

    await service.update_account(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        current_balance=Decimal("1500.00"),
    )

    events = await session.execute(
        sa.select(AuditEvent).where(
            AuditEvent.entity_id == account.id,
            AuditEvent.operation == "update",
        )
    )
    assert events.scalars().first() is not None


async def test_update_account_negative_balance_asset_raises(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, account_type=AccountType.CHECKING)

    with pytest.raises(service.ValidationError):
        await service.update_account(
            session,
            account_id=account.id,
            household_id=hh.id,
            actor_id=user.id,
            current_balance=Decimal("-1"),
        )


async def test_update_account_negative_balance_asset_override(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, account_type=AccountType.CHECKING)

    updated = await service.update_account(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        current_balance=Decimal("-50"),
        allow_negative_balance=True,
    )
    assert updated.current_balance == Decimal("-50")


# ---------------------------------------------------------------------------
# Integration: Soft delete
# ---------------------------------------------------------------------------


async def test_archive_account_excluded_from_default_queries(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)

    await service.archive_account(
        session, account_id=account.id, household_id=hh.id, actor_id=user.id
    )

    accounts = await service.list_accounts(session, household_id=hh.id)
    assert account.id not in [a.id for a in accounts]


async def test_archive_account_visible_with_include_archived(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)

    await service.archive_account(
        session, account_id=account.id, household_id=hh.id, actor_id=user.id
    )

    result = await session.execute(
        sa.select(Account)
        .where(Account.household_id == hh.id)
        .execution_options(include_archived=True)
    )
    ids = [a.id for a in result.scalars().all()]
    assert account.id in ids


# ---------------------------------------------------------------------------
# Integration: Balance reconciliation
# ---------------------------------------------------------------------------


async def test_reconcile_balance_updates_and_emits_audit(session: AsyncSession) -> None:
    from app.audit.models import AuditEvent

    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, current_balance=Decimal("500.00"))

    updated = await service.reconcile_balance(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        new_balance=Decimal("600.00"),
    )
    assert updated.current_balance == Decimal("600.00")

    events = await session.execute(
        sa.select(AuditEvent).where(
            AuditEvent.entity_id == account.id,
            AuditEvent.operation == "update",
        )
    )
    assert events.scalars().first() is not None


async def test_reconcile_balance_liability_allows_negative(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(
        session,
        hh.id,
        user.id,
        account_type=AccountType.CREDIT_CARD,
        current_balance=Decimal("0"),
    )

    updated = await service.reconcile_balance(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        new_balance=Decimal("-2500.00"),
    )
    assert updated.current_balance == Decimal("-2500.00")


# ---------------------------------------------------------------------------
# Integration: AccountGroup CRUD
# ---------------------------------------------------------------------------


async def test_create_account_group(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    group = await service.create_account_group(
        session, household_id=hh.id, actor_id=user.id, name="Joint Checking"
    )
    assert group.id is not None
    assert group.name == "Joint Checking"
    assert group.household_id == hh.id


async def test_create_account_group_with_members(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    a = await _make_account(session, hh.id, user.id, name="Alice Visa")
    b = await _make_account(session, hh.id, user.id, name="Bob Visa")

    group = await service.create_account_group(
        session,
        household_id=hh.id,
        actor_id=user.id,
        name="Joint Visa",
        member_account_ids=[a.id, b.id],
    )

    # Reload accounts to check group linkage
    a_reloaded = await service.get_account(session, account_id=a.id, household_id=hh.id)
    b_reloaded = await service.get_account(session, account_id=b.id, household_id=hh.id)
    assert a_reloaded.account_group_id == group.id
    assert b_reloaded.account_group_id == group.id


async def test_add_remove_account_from_group(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)
    group = await service.create_account_group(
        session, household_id=hh.id, actor_id=user.id, name="Group"
    )

    await service.add_account_to_group(
        session,
        group_id=group.id,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
    )
    linked = await service.get_account(session, account_id=account.id, household_id=hh.id)
    assert linked.account_group_id == group.id

    await service.remove_account_from_group(
        session,
        group_id=group.id,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
    )
    unlinked = await service.get_account(session, account_id=account.id, household_id=hh.id)
    assert unlinked.account_group_id is None


async def test_add_account_to_different_group_raises_conflict(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id)
    g1 = await service.create_account_group(
        session, household_id=hh.id, actor_id=user.id, name="Group 1"
    )
    g2 = await service.create_account_group(
        session, household_id=hh.id, actor_id=user.id, name="Group 2"
    )

    await service.add_account_to_group(
        session,
        group_id=g1.id,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
    )
    with pytest.raises(service.ConflictError):
        await service.add_account_to_group(
            session,
            group_id=g2.id,
            account_id=account.id,
            household_id=hh.id,
            actor_id=user.id,
        )


# ---------------------------------------------------------------------------
# Integration: AccountGroup candidate detection
# ---------------------------------------------------------------------------


async def test_find_group_candidates_same_institution_balance_name(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)

    a = await _make_account(
        session,
        hh.id,
        user.id,
        name="Chase Sapphire",
        institution="Chase",
        current_balance=Decimal("1234.56"),
    )
    b = await _make_account(
        session,
        hh.id,
        user.id,
        name="Chase Sapphire",
        institution="Chase",
        current_balance=Decimal("1234.56"),
    )

    candidates = await service.find_group_candidates(session, household_id=hh.id)
    pairs = {(c.account_a.id, c.account_b.id) for c in candidates}
    pairs |= {(c.account_b.id, c.account_a.id) for c in candidates}
    assert (a.id, b.id) in pairs or (b.id, a.id) in pairs


async def test_find_group_candidates_excludes_already_grouped(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)

    a = await _make_account(session, hh.id, user.id, name="Chase Sapphire", institution="Chase")
    b = await _make_account(session, hh.id, user.id, name="Chase Sapphire", institution="Chase")

    group = await service.create_account_group(
        session,
        household_id=hh.id,
        actor_id=user.id,
        name="Linked",
        member_account_ids=[a.id, b.id],
    )
    assert group is not None

    candidates = await service.find_group_candidates(session, household_id=hh.id)
    assert len(candidates) == 0


async def test_find_group_candidates_different_balance_not_detected(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)

    await _make_account(
        session, hh.id, user.id, name="Checking", institution="Bank", current_balance=Decimal("100")
    )
    await _make_account(
        session, hh.id, user.id, name="Checking", institution="Bank", current_balance=Decimal("200")
    )

    candidates = await service.find_group_candidates(session, household_id=hh.id)
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# Integration: DebtAccount CRUD
# ---------------------------------------------------------------------------


async def test_create_debt_annotation(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(
        session, hh.id, user.id, account_type=AccountType.CREDIT_CARD, name="Visa"
    )

    da, first_balance = await service.create_debt_annotation(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        minimum_payment_strategy=MinimumPaymentStrategy.FROM_STATEMENT,
        statement_day=15,
        due_day=25,
        payoff_target_date=None,
        initial_balance=Decimal("2500.00"),
        initial_apr=Decimal("0.2499"),
        currency="USD",
        term=None,
        promotional_period_end=None,
        effective_from=date(2026, 1, 1),
    )

    assert da.id is not None
    assert da.account_id == account.id
    assert da.statement_day == 15
    assert first_balance.apr == Decimal("0.249900")
    assert first_balance.effective_to is None


async def test_create_debt_annotation_wrong_type_raises(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(
        session, hh.id, user.id, account_type=AccountType.CHECKING, name="Checking"
    )

    with pytest.raises(service.ValidationError, match="debt account type"):
        await service.create_debt_annotation(
            session,
            account_id=account.id,
            household_id=hh.id,
            actor_id=user.id,
            minimum_payment_strategy=MinimumPaymentStrategy.FROM_STATEMENT,
            statement_day=None,
            due_day=None,
            payoff_target_date=None,
            initial_balance=Decimal("0"),
            initial_apr=Decimal("0.10"),
            currency="USD",
            term=None,
            promotional_period_end=None,
            effective_from=date(2026, 1, 1),
        )


async def test_create_debt_annotation_duplicate_raises(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, account_type=AccountType.CREDIT_CARD)
    kwargs = {
        "account_id": account.id,
        "household_id": hh.id,
        "actor_id": user.id,
        "minimum_payment_strategy": MinimumPaymentStrategy.FROM_STATEMENT,
        "statement_day": None,
        "due_day": None,
        "payoff_target_date": None,
        "initial_balance": Decimal("100"),
        "initial_apr": Decimal("0.20"),
        "currency": "USD",
        "term": None,
        "promotional_period_end": None,
        "effective_from": date(2026, 1, 1),
    }
    await service.create_debt_annotation(session, **kwargs)
    with pytest.raises(service.ConflictError):
        await service.create_debt_annotation(session, **kwargs)


async def test_add_debt_balance_closes_previous_row(session: AsyncSession) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, account_type=AccountType.CREDIT_CARD)

    await service.create_debt_annotation(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        minimum_payment_strategy=MinimumPaymentStrategy.FROM_STATEMENT,
        statement_day=None,
        due_day=None,
        payoff_target_date=None,
        initial_balance=Decimal("1000"),
        initial_apr=Decimal("0.2499"),
        currency="USD",
        term=None,
        promotional_period_end=None,
        effective_from=date(2026, 1, 1),
    )

    new_row = await service.add_debt_balance(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        principal_balance=Decimal("900"),
        currency="USD",
        apr=Decimal("0.1999"),
        term=None,
        promotional_period_end=None,
        effective_from=date(2026, 7, 1),
    )

    balances = await service.list_debt_balances(session, account_id=account.id, household_id=hh.id)
    assert len(balances) == 2

    closed = next(b for b in balances if b.effective_to is not None)
    assert closed.effective_to == date(2026, 6, 30)

    assert new_row.effective_to is None


async def test_add_debt_balance_effective_from_must_be_after_current(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    hh = await _make_household(session, user)
    account = await _make_account(session, hh.id, user.id, account_type=AccountType.CREDIT_CARD)

    await service.create_debt_annotation(
        session,
        account_id=account.id,
        household_id=hh.id,
        actor_id=user.id,
        minimum_payment_strategy=MinimumPaymentStrategy.FROM_STATEMENT,
        statement_day=None,
        due_day=None,
        payoff_target_date=None,
        initial_balance=Decimal("500"),
        initial_apr=Decimal("0.2499"),
        currency="USD",
        term=None,
        promotional_period_end=None,
        effective_from=date(2026, 6, 1),
    )

    with pytest.raises(service.ValidationError, match="effective_from"):
        await service.add_debt_balance(
            session,
            account_id=account.id,
            household_id=hh.id,
            actor_id=user.id,
            principal_balance=Decimal("400"),
            currency="USD",
            apr=Decimal("0.05"),
            term=None,
            promotional_period_end=None,
            effective_from=date(2026, 6, 1),  # same as current — must be after
        )


# ---------------------------------------------------------------------------
# Hypothesis: AccountGroup candidate detection property
# ---------------------------------------------------------------------------


@given(
    institution=st.text(min_size=3, max_size=30).filter(lambda s: s.strip()),
    balance=st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("100000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    base_name=st.text(min_size=6, max_size=20).filter(lambda s: s.strip()),
)
@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow])
def test_group_candidate_detection_same_accounts_always_found(
    institution: str,
    balance: Decimal,
    base_name: str,
) -> None:
    """Accounts with identical institution, balance, and name are always candidates."""

    async def _run() -> None:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

        with PostgresContainer("postgres:16") as pg:
            url = "postgresql+asyncpg://" + pg.get_connection_url().split("://", 1)[1]
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as s:
                user = await households_service.create_user(
                    s,
                    email=f"u_{uuid.uuid4().hex[:8]}@t.com",
                    display_name="U",
                    password="pw12345678",  # pragma: allowlist secret
                )
                hh = await households_service.create_household(
                    s,
                    name="HH",
                    visibility_mode=VisibilityMode.FULLY_SHARED,
                    home_currency="USD",
                    owner=user,
                )
                a = await service.create_account(
                    s,
                    household_id=hh.id,
                    actor_id=user.id,
                    name=base_name,
                    institution=institution,
                    account_type=AccountType.CHECKING,
                    currency="USD",
                    current_balance=balance,
                )
                b = await service.create_account(
                    s,
                    household_id=hh.id,
                    actor_id=user.id,
                    name=base_name,
                    institution=institution,
                    account_type=AccountType.CHECKING,
                    currency="USD",
                    current_balance=balance,
                )

                candidates = await service.find_group_candidates(s, household_id=hh.id)
                all_pairs = set()
                for c in candidates:
                    all_pairs.add((c.account_a.id, c.account_b.id))
                    all_pairs.add((c.account_b.id, c.account_a.id))

                assert (a.id, b.id) in all_pairs

        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Hypothesis: APR history no gaps / no overlaps
# ---------------------------------------------------------------------------


@given(
    n_updates=st.integers(min_value=2, max_value=5),
    start_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 1, 1)),
    gap_days=st.lists(st.integers(min_value=20, max_value=60), min_size=4, max_size=4),
)
@settings(max_examples=12, suppress_health_check=[HealthCheck.too_slow])
def test_apr_history_no_gaps_no_overlaps(
    n_updates: int,
    start_date: date,
    gap_days: list[int],
) -> None:
    """After N APR updates, exactly one current row and chain is contiguous."""

    async def _run() -> None:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

        with PostgresContainer("postgres:16") as pg:
            url = "postgresql+asyncpg://" + pg.get_connection_url().split("://", 1)[1]
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as s:
                user = await households_service.create_user(
                    s,
                    email=f"u_{uuid.uuid4().hex[:8]}@t.com",
                    display_name="U",
                    password="pw12345678",  # pragma: allowlist secret
                )
                hh = await households_service.create_household(
                    s,
                    name="HH",
                    visibility_mode=VisibilityMode.FULLY_SHARED,
                    home_currency="USD",
                    owner=user,
                )
                account = await service.create_account(
                    s,
                    household_id=hh.id,
                    actor_id=user.id,
                    name="Visa",
                    institution="Bank",
                    account_type=AccountType.CREDIT_CARD,
                    currency="USD",
                    current_balance=Decimal("1000"),
                )
                await service.create_debt_annotation(
                    s,
                    account_id=account.id,
                    household_id=hh.id,
                    actor_id=user.id,
                    minimum_payment_strategy=MinimumPaymentStrategy.FROM_STATEMENT,
                    statement_day=None,
                    due_day=None,
                    payoff_target_date=None,
                    initial_balance=Decimal("1000"),
                    initial_apr=Decimal("0.2499"),
                    currency="USD",
                    term=None,
                    promotional_period_end=None,
                    effective_from=start_date,
                )

                current_date = start_date + timedelta(days=gap_days[0])
                for i in range(n_updates - 1):
                    await service.add_debt_balance(
                        s,
                        account_id=account.id,
                        household_id=hh.id,
                        actor_id=user.id,
                        principal_balance=Decimal("900"),
                        currency="USD",
                        apr=Decimal("0.1999"),
                        term=None,
                        promotional_period_end=None,
                        effective_from=current_date,
                    )
                    current_date += timedelta(days=gap_days[min(i + 1, 3)])

                balances = await service.list_debt_balances(
                    s, account_id=account.id, household_id=hh.id
                )
                assert len(balances) == n_updates

                # Exactly one current row
                current_rows = [b for b in balances if b.effective_to is None]
                assert len(current_rows) == 1, "Must have exactly one current row"

                # Contiguous chain: each closed row's effective_to = next row's effective_from - 1
                sorted_rows = sorted(balances, key=lambda b: b.effective_from)
                for i in range(len(sorted_rows) - 1):
                    expected_et = sorted_rows[i + 1].effective_from - timedelta(days=1)
                    assert sorted_rows[i].effective_to == expected_et, (
                        f"Gap/overlap between rows {i} and {i + 1}: "
                        f"effective_to={sorted_rows[i].effective_to} "
                        f"expected={expected_et}"
                    )

        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Hypothesis: Soft delete always excludes archived accounts
# ---------------------------------------------------------------------------


@given(
    n_accounts=st.integers(min_value=1, max_value=5),
    archive_indices=st.lists(st.integers(min_value=0, max_value=4), min_size=1, max_size=3),
)
@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow])
def test_soft_delete_always_excludes_archived(
    n_accounts: int,
    archive_indices: list[int],
) -> None:
    """Archived accounts never appear in default list queries."""
    archive_set = {i for i in archive_indices if i < n_accounts}

    async def _run() -> None:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

        with PostgresContainer("postgres:16") as pg:
            url = "postgresql+asyncpg://" + pg.get_connection_url().split("://", 1)[1]
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as s:
                user = await households_service.create_user(
                    s,
                    email=f"u_{uuid.uuid4().hex[:8]}@t.com",
                    display_name="U",
                    password="pw12345678",  # pragma: allowlist secret
                )
                hh = await households_service.create_household(
                    s,
                    name="HH",
                    visibility_mode=VisibilityMode.FULLY_SHARED,
                    home_currency="USD",
                    owner=user,
                )
                accounts = []
                for i in range(n_accounts):
                    acc = await service.create_account(
                        s,
                        household_id=hh.id,
                        actor_id=user.id,
                        name=f"Account {i}",
                        institution="Bank",
                        account_type=AccountType.CHECKING,
                        currency="USD",
                        current_balance=Decimal("100"),
                    )
                    accounts.append(acc)

                archived_ids = set()
                for idx in archive_set:
                    await service.archive_account(
                        s,
                        account_id=accounts[idx].id,
                        household_id=hh.id,
                        actor_id=user.id,
                    )
                    archived_ids.add(accounts[idx].id)

                live_accounts = await service.list_accounts(s, household_id=hh.id)
                live_ids = {a.id for a in live_accounts}

                assert archived_ids.isdisjoint(
                    live_ids
                ), f"Archived accounts appeared in default query: {archived_ids & live_ids}"

        await engine.dispose()

    asyncio.run(_run())
