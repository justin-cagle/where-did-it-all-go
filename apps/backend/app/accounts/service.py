"""Accounts service layer.

No database joins across module boundaries. All cross-module communication
goes through published interfaces (see architecture.md).
"""

import difflib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.enums import ASSET_ACCOUNT_TYPES, AccountType, MinimumPaymentStrategy
from app.accounts.models import Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount
from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.audit.models import AuditEvent


class NotFoundError(Exception):
    """Entity does not exist or is not visible."""


class ConflictError(Exception):
    """Operation would violate a uniqueness or state constraint."""


class ValidationError(Exception):
    """Operation violates a domain invariant."""


# ---------------------------------------------------------------------------
# Pure validation helpers (testable without DB)
# ---------------------------------------------------------------------------


def validate_balance(
    account_type: AccountType,
    new_balance: Decimal,
    allow_negative: bool,
) -> None:
    """Raise ValidationError if the balance update violates domain invariants.

    Asset accounts (checking, savings, investment, manual, other) must not go
    negative without an explicit override. Liability accounts allow any sign.
    """
    if account_type in ASSET_ACCOUNT_TYPES and new_balance < Decimal(0) and not allow_negative:
        raise ValidationError(
            f"balance cannot be negative for {account_type} accounts without allow_negative=True"
        )


# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------


async def create_account(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    institution: str | None,
    account_type: AccountType,
    currency: str,
    current_balance: Decimal,
) -> Account:
    """Create an account and, for MANUAL type, its ManualAccount annotation."""
    is_manual = account_type == AccountType.MANUAL
    account = Account(
        household_id=household_id,
        name=name,
        institution=institution,
        account_type=str(account_type),
        currency=currency.upper(),
        current_balance=current_balance,
        is_manual=is_manual,
    )
    session.add(account)
    await session.flush()

    if is_manual:
        manual = ManualAccount(account_id=account.id)
        session.add(manual)
        await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account",
        entity_id=account.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/name", "value": name},
            {"op": "add", "path": "/account_type", "value": str(account_type)},
            {"op": "add", "path": "/currency", "value": currency.upper()},
            {"op": "add", "path": "/current_balance", "value": str(current_balance)},
        ],
    )
    return account


async def get_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
) -> Account:
    """Return an account scoped to the household. Raises NotFoundError if absent."""
    result = await session.execute(
        sa.select(Account).where(
            Account.id == account_id,
            Account.household_id == household_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise NotFoundError("account not found")
    return account


async def list_accounts(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_type: AccountType | None = None,
    is_manual: bool | None = None,
) -> list[Account]:
    """Return accounts in the household, optionally filtered by type or manual flag."""
    stmt = sa.select(Account).where(Account.household_id == household_id)
    if account_type is not None:
        stmt = stmt.where(Account.account_type == str(account_type))
    if is_manual is not None:
        stmt = stmt.where(Account.is_manual == is_manual)
    stmt = stmt.order_by(Account.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    current_balance: Decimal | None = None,
    allow_negative_balance: bool = False,
) -> Account:
    """Update name and/or balance. Balance update enforces the no-negative invariant."""
    account = await get_account(session, account_id=account_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    if name is not None:
        delta.append({"op": "replace", "path": "/name", "value": name})
        account.name = name

    if current_balance is not None:
        validate_balance(AccountType(account.account_type), current_balance, allow_negative_balance)
        delta.append({"op": "replace", "path": "/current_balance", "value": str(current_balance)})
        account.current_balance = current_balance

    await session.flush()

    if delta:
        await _write_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_type="account",
            entity_id=account.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return account


async def archive_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete an account."""
    account = await get_account(session, account_id=account_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    account.archived_at = now
    account.archived_by = actor_id
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account",
        entity_id=account_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Balance reconciliation
# ---------------------------------------------------------------------------


async def reconcile_balance(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    new_balance: Decimal,
    allow_negative: bool = False,
) -> Account:
    """Set current_balance and emit an audit delta recording the before/after."""
    account = await get_account(session, account_id=account_id, household_id=household_id)
    validate_balance(AccountType(account.account_type), new_balance, allow_negative)

    old_balance = account.current_balance
    account.current_balance = new_balance
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account",
        entity_id=account_id,
        operation=AuditOperation.UPDATE,
        delta=[
            {"op": "test", "path": "/current_balance", "value": str(old_balance)},
            {"op": "replace", "path": "/current_balance", "value": str(new_balance)},
        ],
    )
    return account


# ---------------------------------------------------------------------------
# AccountGroup CRUD
# ---------------------------------------------------------------------------


async def create_account_group(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    primary_holder_id: uuid.UUID | None = None,
    authorized_user_ids: list[uuid.UUID] | None = None,
    member_account_ids: list[uuid.UUID] | None = None,
) -> AccountGroup:
    """Create an account group, optionally linking initial member accounts."""
    group = AccountGroup(
        household_id=household_id,
        name=name,
        primary_holder_id=primary_holder_id,
        authorized_user_ids=[str(uid) for uid in (authorized_user_ids or [])],
    )
    session.add(group)
    await session.flush()

    for acct_id in member_account_ids or []:
        acct = await get_account(session, account_id=acct_id, household_id=household_id)
        if acct.account_group_id is not None and acct.account_group_id != group.id:
            raise ConflictError(f"account {acct_id} already belongs to a different group")
        acct.account_group_id = group.id
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account_group",
        entity_id=group.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
    )
    return group


async def get_account_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> AccountGroup:
    """Return an account group scoped to the household."""
    result = await session.execute(
        sa.select(AccountGroup).where(
            AccountGroup.id == group_id,
            AccountGroup.household_id == household_id,
        )
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise NotFoundError("account group not found")
    return group


async def list_account_groups(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[AccountGroup]:
    """Return all account groups for the household."""
    result = await session.execute(
        sa.select(AccountGroup)
        .where(AccountGroup.household_id == household_id)
        .order_by(AccountGroup.created_at)
    )
    return list(result.scalars().all())


async def update_account_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    primary_holder_id: uuid.UUID | None = None,
    authorized_user_ids: list[uuid.UUID] | None = None,
) -> AccountGroup:
    """Update name, primary holder, or authorized users list."""
    group = await get_account_group(session, group_id=group_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    if name is not None:
        delta.append({"op": "replace", "path": "/name", "value": name})
        group.name = name
    if primary_holder_id is not None:
        delta.append(
            {"op": "replace", "path": "/primary_holder_id", "value": str(primary_holder_id)}
        )
        group.primary_holder_id = primary_holder_id
    if authorized_user_ids is not None:
        ids = [str(uid) for uid in authorized_user_ids]
        delta.append({"op": "replace", "path": "/authorized_user_ids", "value": ids})
        group.authorized_user_ids = ids

    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_type="account_group",
            entity_id=group_id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return group


async def archive_account_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete an account group."""
    group = await get_account_group(session, group_id=group_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    group.archived_at = now
    group.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account_group",
        entity_id=group_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


async def add_account_to_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Account:
    """Link an account to a group. Raises ConflictError if already in a different group."""
    group = await get_account_group(session, group_id=group_id, household_id=household_id)
    account = await get_account(session, account_id=account_id, household_id=household_id)
    if account.account_group_id is not None and account.account_group_id != group.id:
        raise ConflictError("account already belongs to a different group")
    account.account_group_id = group.id
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account",
        entity_id=account_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/account_group_id", "value": str(group_id)}],
    )
    return account


async def remove_account_from_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Account:
    """Unlink an account from its group."""
    account = await get_account(session, account_id=account_id, household_id=household_id)
    if account.account_group_id != group_id:
        raise NotFoundError("account is not in this group")
    account.account_group_id = None
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="account",
        entity_id=account_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/account_group_id", "value": None}],
    )
    return account


# ---------------------------------------------------------------------------
# AccountGroup candidate detection
# ---------------------------------------------------------------------------


@dataclass
class GroupCandidate:
    """Candidate pair of accounts that may represent the same underlying account."""

    account_a: Account
    account_b: Account
    reason: str
    similarity_score: float


async def find_group_candidates(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[GroupCandidate]:
    """Return candidate account pairs for grouping based on heuristics.

    Heuristic: same institution + same balance + same currency + name similarity ≥ 0.6.
    Candidates are surfaced for HITL review. Never auto-merges.
    """
    accounts = await list_accounts(session, household_id=household_id)
    ungrouped = [a for a in accounts if a.account_group_id is None and a.institution is not None]

    candidates: list[GroupCandidate] = []
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for i, a in enumerate(ungrouped):
        for b in ungrouped[i + 1 :]:
            if a.institution != b.institution:
                continue
            if a.currency != b.currency:
                continue
            if a.current_balance != b.current_balance:
                continue
            similarity = difflib.SequenceMatcher(None, a.name.lower(), b.name.lower()).ratio()
            if similarity < 0.6:
                continue
            key: tuple[uuid.UUID, uuid.UUID] = (min(a.id, b.id), max(a.id, b.id))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                GroupCandidate(
                    account_a=a,
                    account_b=b,
                    reason=(
                        f"same institution '{a.institution}', "
                        f"same balance {a.current_balance} {a.currency}, "
                        f"name similarity {similarity:.0%}"
                    ),
                    similarity_score=similarity,
                )
            )

    return candidates


# ---------------------------------------------------------------------------
# DebtAccount CRUD
# ---------------------------------------------------------------------------


async def create_debt_annotation(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    minimum_payment_strategy: MinimumPaymentStrategy,
    statement_day: int | None,
    due_day: int | None,
    payoff_target_date: date | None,
    initial_balance: Decimal,
    initial_apr: Decimal,
    currency: str,
    term: int | None,
    promotional_period_end: date | None,
    effective_from: date,
) -> tuple[DebtAccount, DebtBalance]:
    """Annotate a debt account and create the initial APR tranche."""
    account = await get_account(session, account_id=account_id, household_id=household_id)
    account_type = AccountType(account.account_type)
    if account_type not in (AccountType.CREDIT_CARD, AccountType.LOAN, AccountType.LINE_OF_CREDIT):
        raise ValidationError(
            f"debt annotation requires a debt account type (credit_card, loan, line_of_credit); "
            f"got {account_type}"
        )

    existing = await _get_debt_account_by_account_id(session, account_id)
    if existing is not None:
        raise ConflictError("debt annotation already exists for this account")

    debt_account = DebtAccount(
        account_id=account_id,
        minimum_payment_strategy=str(minimum_payment_strategy),
        statement_day=statement_day,
        due_day=due_day,
        payoff_target_date=payoff_target_date,
    )
    session.add(debt_account)
    await session.flush()

    balance = DebtBalance(
        debt_account_id=debt_account.id,
        principal_balance=initial_balance,
        currency=currency.upper(),
        apr=initial_apr,
        term=term,
        promotional_period_end=promotional_period_end,
        effective_from=effective_from,
        effective_to=None,
    )
    session.add(balance)
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="debt_account",
        entity_id=debt_account.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/account_id", "value": str(account_id)},
            {"op": "add", "path": "/initial_apr", "value": str(initial_apr)},
            {"op": "add", "path": "/effective_from", "value": str(effective_from)},
        ],
    )
    return debt_account, balance


async def get_debt_annotation(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
) -> DebtAccount:
    """Return the debt annotation for an account, verifying household scope."""
    await get_account(session, account_id=account_id, household_id=household_id)
    da = await _get_debt_account_by_account_id(session, account_id)
    if da is None:
        raise NotFoundError("no debt annotation for this account")
    return da


async def update_debt_annotation(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    minimum_payment_strategy: MinimumPaymentStrategy | None = None,
    statement_day: int | None = None,
    due_day: int | None = None,
    payoff_target_date: date | None = None,
) -> DebtAccount:
    """Update payment strategy or scheduling fields on the debt annotation."""
    da = await get_debt_annotation(session, account_id=account_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    if minimum_payment_strategy is not None:
        delta.append(
            {
                "op": "replace",
                "path": "/minimum_payment_strategy",
                "value": str(minimum_payment_strategy),
            }
        )
        da.minimum_payment_strategy = str(minimum_payment_strategy)
    if statement_day is not None:
        delta.append({"op": "replace", "path": "/statement_day", "value": statement_day})
        da.statement_day = statement_day
    if due_day is not None:
        delta.append({"op": "replace", "path": "/due_day", "value": due_day})
        da.due_day = due_day
    if payoff_target_date is not None:
        delta.append(
            {"op": "replace", "path": "/payoff_target_date", "value": str(payoff_target_date)}
        )
        da.payoff_target_date = payoff_target_date

    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_type="debt_account",
            entity_id=da.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return da


async def list_debt_balances(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[DebtBalance]:
    """Return full APR history for a debt account, ordered by effective_from."""
    da = await get_debt_annotation(session, account_id=account_id, household_id=household_id)
    result = await session.execute(
        sa.select(DebtBalance)
        .where(DebtBalance.debt_account_id == da.id)
        .order_by(DebtBalance.effective_from)
    )
    return list(result.scalars().all())


async def add_debt_balance(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    principal_balance: Decimal,
    currency: str,
    apr: Decimal,
    term: int | None,
    promotional_period_end: date | None,
    effective_from: date,
) -> DebtBalance:
    """Add a new APR version, closing the current row in the effective-dated chain.

    Creates a contiguous history: the current row's effective_to is set to
    effective_from - 1 day before the new row is inserted.
    """
    da = await get_debt_annotation(session, account_id=account_id, household_id=household_id)

    current_result = await session.execute(
        sa.select(DebtBalance).where(
            DebtBalance.debt_account_id == da.id,
            DebtBalance.effective_to.is_(None),
        )
    )
    current = current_result.scalar_one_or_none()

    if current is not None:
        if effective_from <= current.effective_from:
            raise ValidationError(
                f"effective_from {effective_from} must be after the current row's "
                f"effective_from {current.effective_from}"
            )
        current.effective_to = effective_from - timedelta(days=1)
        await session.flush()

    new_balance = DebtBalance(
        debt_account_id=da.id,
        principal_balance=principal_balance,
        currency=currency.upper(),
        apr=apr,
        term=term,
        promotional_period_end=promotional_period_end,
        effective_from=effective_from,
        effective_to=None,
    )
    session.add(new_balance)
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="debt_balance",
        entity_id=new_balance.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/apr", "value": str(apr)},
            {"op": "add", "path": "/effective_from", "value": str(effective_from)},
            {"op": "add", "path": "/principal_balance", "value": str(principal_balance)},
        ],
    )
    return new_balance


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_debt_account_by_account_id(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> DebtAccount | None:
    result = await session.execute(
        sa.select(DebtAccount).where(DebtAccount.account_id == account_id)
    )
    return result.scalar_one_or_none()


@dataclass
class BalancePoint:
    date: date
    balance: Decimal


async def get_balance_history(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[BalancePoint]:
    """Return one balance reading per day for the last 90 days.

    Reads from the audit log — only days where a balance-reconciliation event
    occurred appear in the result. If no such events exist, returns empty list.
    """
    account = await session.get(Account, account_id)
    if account is None or account.archived_at is not None or account.household_id != household_id:
        raise NotFoundError(f"account {account_id} not found")

    cutoff = datetime.now(tz=UTC) - timedelta(days=90)
    stmt = (
        sa.select(AuditEvent)
        .where(
            AuditEvent.entity_type == "account",
            AuditEvent.entity_id == account_id,
            AuditEvent.occurred_at >= cutoff,
        )
        .order_by(AuditEvent.occurred_at.asc())
    )
    rows = await session.execute(stmt)
    events = list(rows.scalars().all())

    by_day: dict[date, Decimal] = {}
    for event in events:
        for raw_op in event.delta:
            if not isinstance(raw_op, dict):
                continue
            op = cast(dict[str, Any], raw_op)
            if op.get("path") != "/current_balance":
                continue
            if op.get("op") not in ("replace", "add"):
                continue
            try:
                balance = Decimal(str(op["value"]))
                day = event.occurred_at.date()
                by_day[day] = balance
            except (ValueError, KeyError, TypeError):
                pass

    return [BalancePoint(date=d, balance=b) for d, b in sorted(by_day.items())]


async def _write_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    household_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    operation: AuditOperation,
    delta: list[dict[str, Any]],
    rationale: str | None = None,
) -> None:
    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        delta=delta,
        rationale=rationale,
        actor_id=actor_id,
    )
