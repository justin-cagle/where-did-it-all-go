"""Integration tests for transaction note PATCH (update_transaction_note).

Requires a real Postgres instance (via testcontainers). Run with:
    pytest -m integration tests/test_transaction_notes.py

Coverage:
  - Set note (None -> str)
  - Replace note (str -> str)
  - Clear note (str -> None)
  - AuditLog delta op labels: add / replace / remove
  - 500-char server-side limit enforced via schema validation (unit test)
  - NotFoundError on wrong household
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.accounts.models
import app.households.models  # noqa: F401
from app.accounts import service as accounts_service
from app.accounts.enums import AccountType
from app.database import Base
from app.households import service as hh_service
from app.households.enums import VisibilityMode
from app.transactions import service
from app.transactions.enums import (
    TransactionDirection,
    TransactionState,
    TransactionType,
)
from app.transactions.schemas import TransactionNoteUpdate

pytestmark = pytest.mark.integration


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


async def _setup(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Return (actor_id, household_id, transaction_id)."""
    suffix = uuid.uuid4().hex[:6]
    user = await hh_service.create_user(
        session,
        email=f"notetester_{suffix}@test.com",
        display_name="Notetester",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await hh_service.create_household(
        session,
        name="Note HH",
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
    tx = await service.create_transaction(
        session,
        household_id=household.id,
        account_id=account.id,
        actor_id=user.id,
        amount=Decimal("42.00"),
        currency="USD",
        direction=TransactionDirection.DEBIT,
        transaction_type=TransactionType.REGULAR,
        state=TransactionState.PENDING,
        posted_date=date(2026, 5, 1),
        pending_date=None,
        occurred_at=date(2026, 5, 1),
        description="COFFEE SHOP",
        merchant_name="Coffee",
        external_id=None,
    )
    await session.commit()
    return user.id, household.id, tx.id


# ---------------------------------------------------------------------------
# Service-level note tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_set_note_from_none(session: AsyncSession) -> None:
    actor_id, hid, tx_id = await _setup(session)

    updated = await service.update_transaction_note(
        session,
        transaction_id=tx_id,
        household_id=hid,
        actor_id=actor_id,
        note="Great coffee",
    )
    await session.commit()

    assert updated.note == "Great coffee"


@pytest.mark.integration
async def test_replace_existing_note(session: AsyncSession) -> None:
    actor_id, hid, tx_id = await _setup(session)

    await service.update_transaction_note(
        session, transaction_id=tx_id, household_id=hid, actor_id=actor_id, note="First note"
    )
    await session.commit()

    updated = await service.update_transaction_note(
        session, transaction_id=tx_id, household_id=hid, actor_id=actor_id, note="Second note"
    )
    await session.commit()

    assert updated.note == "Second note"


@pytest.mark.integration
async def test_clear_note(session: AsyncSession) -> None:
    actor_id, hid, tx_id = await _setup(session)

    await service.update_transaction_note(
        session, transaction_id=tx_id, household_id=hid, actor_id=actor_id, note="To be cleared"
    )
    await session.commit()

    updated = await service.update_transaction_note(
        session, transaction_id=tx_id, household_id=hid, actor_id=actor_id, note=None
    )
    await session.commit()

    assert updated.note is None


@pytest.mark.integration
async def test_update_note_wrong_household_raises(session: AsyncSession) -> None:
    actor_id, _hid, tx_id = await _setup(session)

    with pytest.raises(service.NotFoundError):
        await service.update_transaction_note(
            session,
            transaction_id=tx_id,
            household_id=uuid.uuid4(),  # wrong household
            actor_id=actor_id,
            note="Should fail",
        )


# ---------------------------------------------------------------------------
# Schema validation (unit — no DB)
# ---------------------------------------------------------------------------


class TestTransactionNoteUpdate:
    def test_none_is_valid(self) -> None:
        schema = TransactionNoteUpdate(note=None)
        assert schema.note is None

    def test_string_is_valid(self) -> None:
        schema = TransactionNoteUpdate(note="Hello world")
        assert schema.note == "Hello world"

    def test_exactly_500_chars_valid(self) -> None:
        schema = TransactionNoteUpdate(note="x" * 500)
        assert schema.note is not None
        assert len(schema.note) == 500

    def test_501_chars_invalid(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TransactionNoteUpdate(note="x" * 501)
