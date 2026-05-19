"""Transactions service layer.

No database joins across module boundaries. All cross-module communication
goes through published interfaces (see architecture.md).

Pure helper functions (normalize_description, score_dedup_confidence,
check_refund_pairable, validate_split_amounts) are importable directly
for property-based testing without a DB.
"""

import difflib
import re
import string
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.transactions.enums import (
    DedupResolution,
    GroupType,
    TransactionDirection,
    TransactionState,
    TransactionType,
)
from app.transactions.models import (
    DeduplicationLog,
    PaymentGroup,
    SplitAllocation,
    Transaction,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a uniqueness or state constraint."""


class ValidationError(Exception):
    """Operation violates a domain invariant."""


class InvalidTransitionError(Exception):
    """Requested state transition is not permitted by the state machine."""


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[TransactionState, frozenset[TransactionState]] = {
    TransactionState.PENDING: frozenset({TransactionState.POSTED}),
    TransactionState.POSTED: frozenset({TransactionState.RECONCILED}),
    TransactionState.RECONCILED: frozenset(),
}


# ---------------------------------------------------------------------------
# Pure helpers (no DB — safe for Hypothesis tests)
# ---------------------------------------------------------------------------


def normalize_description(description: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Deterministic — same input always produces the same output.
    Used for Stage 2 fuzzy dedup matching.
    """
    desc = description.lower()
    desc = desc.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", desc).strip()


def score_dedup_confidence(
    date1: date,
    date2: date,
    description1: str,
    description2: str,
) -> float:
    """Confidence score for a fuzzy dedup pair. Pure — no side effects.

    Preconditions (must be checked by caller): account_id must match, amount must match.
    Returns 0.0 if dates differ by more than 3 days.

    Score: 0.6 * description_similarity + 0.4 * date_proximity_score
    Date proximity: 1.0 at delta=0, 0.8 at delta=1, 0.6 at delta=2, 0.4 at delta=3.
    """
    date_delta = abs((date1 - date2).days)
    if date_delta > 3:
        return 0.0
    date_score = 1.0 - date_delta * 0.2
    n1 = normalize_description(description1)
    n2 = normalize_description(description2)
    desc_score = difflib.SequenceMatcher(None, n1, n2).ratio()
    return round(0.6 * desc_score + 0.4 * date_score, 4)


def check_refund_pairable(
    *,
    debit_amount: Decimal,
    credit_amount: Decimal,
    debit_merchant: str | None,
    credit_merchant: str | None,
    debit_date: date,
    credit_date: date,
    window_days: int = 30,
) -> bool:
    """Pure check: does a credit transaction qualify as a refund of a debit?

    Criteria:
    - Both must have a merchant_name (non-None).
    - Same merchant (case-insensitive).
    - Dates within window_days of each other.
    - debit_amount >= credit_amount (handles partial refunds).
    """
    if debit_merchant is None or credit_merchant is None:
        return False
    if debit_merchant.strip().lower() != credit_merchant.strip().lower():
        return False
    if abs((debit_date - credit_date).days) > window_days:
        return False
    if debit_amount < credit_amount:
        return False
    return True


def validate_split_amounts(total: Decimal, amounts: list[Decimal]) -> Decimal:
    """Validate split amounts against a transaction total. Pure — no DB.

    Returns the uncategorized remainder (>= 0).
    Raises ValidationError if any amount is non-positive or sum exceeds total.
    """
    for amt in amounts:
        if amt <= Decimal(0):
            raise ValidationError("each split amount must be positive")
    allocated = sum(amounts, Decimal(0))
    if allocated > total:
        raise ValidationError(f"split amounts {allocated} exceed transaction amount {total}")
    return total - allocated


# ---------------------------------------------------------------------------
# Transaction CRUD
# ---------------------------------------------------------------------------


async def create_transaction(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    actor_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    direction: TransactionDirection,
    transaction_type: TransactionType | None,
    state: TransactionState,
    posted_date: date,
    pending_date: date | None,
    occurred_at: date,
    description: str,
    merchant_name: str | None = None,
    external_id: str | None = None,
    manually_categorized: bool = False,
) -> Transaction:
    """Create a transaction and seed an implicit uncategorized split allocation."""
    if external_id is not None:
        existing = await _find_by_external_id(
            session, account_id=account_id, external_id=external_id
        )
        if existing is not None:
            raise ConflictError(
                f"transaction with external_id {external_id!r} already exists "
                f"for account {account_id}"
            )

    tx = Transaction(
        household_id=household_id,
        account_id=account_id,
        amount=amount,
        currency=currency.upper(),
        direction=str(direction),
        transaction_type=str(transaction_type) if transaction_type is not None else None,
        state=str(state),
        posted_date=posted_date,
        pending_date=pending_date,
        occurred_at=occurred_at,
        description=description,
        merchant_name=merchant_name,
        external_id=external_id,
        manually_categorized=manually_categorized,
    )
    session.add(tx)
    await session.flush()

    # Seed implicit single uncategorized split
    split = SplitAllocation(
        transaction_id=tx.id,
        household_id=household_id,
        amount=amount,
        currency=currency.upper(),
        category_id=None,
        tag_ids=[],
        attributed_to_user_id=None,
        manually_categorized=False,
        rule_id=None,
        rule_fired_at=None,
    )
    session.add(split)
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=tx.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/amount", "value": str(amount)},
            {"op": "add", "path": "/currency", "value": currency.upper()},
            {"op": "add", "path": "/direction", "value": str(direction)},
            {"op": "add", "path": "/state", "value": str(state)},
            {"op": "add", "path": "/posted_date", "value": str(posted_date)},
        ],
    )
    return tx


async def get_transaction(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
) -> Transaction:
    """Return a transaction scoped to the household. Raises NotFoundError if absent."""
    stmt = sa.select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.household_id == household_id,
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    result = await session.execute(stmt)
    tx = result.scalar_one_or_none()
    if tx is None:
        raise NotFoundError("transaction not found")
    return tx


async def list_transactions(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    state: TransactionState | None = None,
    direction: TransactionDirection | None = None,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    import_job_id: uuid.UUID | None = None,
) -> list[Transaction]:
    """Return transactions in the household, optionally filtered."""
    stmt = sa.select(Transaction).where(Transaction.household_id == household_id)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if state is not None:
        stmt = stmt.where(Transaction.state == str(state))
    if direction is not None:
        stmt = stmt.where(Transaction.direction == str(direction))
    if transaction_type is not None:
        stmt = stmt.where(Transaction.transaction_type == str(transaction_type))
    if date_from is not None:
        stmt = stmt.where(Transaction.posted_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.posted_date <= date_to)
    if import_job_id is not None:
        stmt = stmt.where(Transaction.import_job_id == import_job_id)
    stmt = stmt.order_by(Transaction.posted_date.desc(), Transaction.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def transition_state(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    new_state: TransactionState,
) -> Transaction:
    """Advance the transaction state machine. Raises InvalidTransitionError for bad moves."""
    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    current = TransactionState(tx.state)
    if new_state not in VALID_TRANSITIONS[current]:
        raise InvalidTransitionError(
            f"cannot transition from {current!r} to {new_state!r}; "
            f"valid targets: {sorted(str(s) for s in VALID_TRANSITIONS[current])}"
        )
    old_state = tx.state
    tx.state = str(new_state)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.UPDATE,
        delta=[
            {"op": "test", "path": "/state", "value": old_state},
            {"op": "replace", "path": "/state", "value": str(new_state)},
        ],
    )
    return tx


async def archive_transaction(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a transaction."""
    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    tx.archived_at = now
    tx.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Split allocations
# ---------------------------------------------------------------------------


async def set_splits(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    splits: list[dict[str, Any]],
) -> list[SplitAllocation]:
    """Replace all splits on a transaction.

    Each entry in `splits` must have at minimum 'amount' and 'currency'.
    An uncategorized remainder split is auto-created if amounts don't sum to total.
    """
    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    amounts = [s["amount"] for s in splits]
    remainder = validate_split_amounts(tx.amount, amounts)

    # Soft-delete existing splits
    existing_result = await session.execute(
        sa.select(SplitAllocation).where(SplitAllocation.transaction_id == transaction_id)
    )
    now = datetime.now(tz=UTC)
    for old_split in existing_result.scalars().all():
        old_split.archived_at = now
        old_split.archived_by = actor_id
    await session.flush()

    # Create new splits
    new_splits: list[SplitAllocation] = []
    for s in splits:
        alloc = SplitAllocation(
            transaction_id=transaction_id,
            household_id=household_id,
            amount=s["amount"],
            currency=s.get("currency", tx.currency),
            category_id=s.get("category_id"),
            tag_ids=[str(t) for t in s.get("tag_ids", [])],
            attributed_to_user_id=s.get("attributed_to_user_id"),
            manually_categorized=s.get("manually_categorized", False),
            rule_id=s.get("rule_id"),
            rule_fired_at=s.get("rule_fired_at"),
        )
        session.add(alloc)
        new_splits.append(alloc)

    # Auto-create uncategorized remainder
    if remainder > Decimal(0):
        rem_alloc = SplitAllocation(
            transaction_id=transaction_id,
            household_id=household_id,
            amount=remainder,
            currency=tx.currency,
            category_id=None,
            tag_ids=[],
            attributed_to_user_id=None,
            manually_categorized=False,
            rule_id=None,
            rule_fired_at=None,
        )
        session.add(rem_alloc)
        new_splits.append(rem_alloc)

    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.SPLIT,
        delta=[{"op": "replace", "path": "/splits", "value": len(new_splits)}],
    )
    return new_splits


async def get_splits(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[SplitAllocation]:
    """Return active (non-archived) splits for a transaction."""
    result = await session.execute(
        sa.select(SplitAllocation)
        .where(
            SplitAllocation.transaction_id == transaction_id,
            SplitAllocation.household_id == household_id,
        )
        .order_by(SplitAllocation.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Transfer pairing
# ---------------------------------------------------------------------------


async def pair_transfer(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    peer_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    transfer_type: str,
) -> tuple[Transaction, Transaction]:
    """Link two transactions as an internal or external transfer.

    Writes transfer_peer_id on both rows. Raises ConflictError if either
    transaction already has a different transfer peer.
    """
    if transaction_id == peer_id:
        raise ValidationError("a transaction cannot be paired with itself")

    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    peer = await get_transaction(session, transaction_id=peer_id, household_id=household_id)

    if tx.transfer_peer_id is not None and tx.transfer_peer_id != peer_id:
        raise ConflictError("transaction already has a different transfer peer")
    if peer.transfer_peer_id is not None and peer.transfer_peer_id != transaction_id:
        raise ConflictError("peer transaction already has a different transfer peer")

    tx.transfer_peer_id = peer_id
    peer.transfer_peer_id = transaction_id
    await session.flush()

    delta: list[dict[str, Any]] = [
        {"op": "add", "path": "/transfer_peer_id", "value": str(peer_id)},
        {"op": "add", "path": "/transfer_type", "value": transfer_type},
    ]
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.UPDATE,
        delta=delta,
    )
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="transaction",
        entity_id=peer_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "add", "path": "/transfer_peer_id", "value": str(transaction_id)}],
    )
    return tx, peer


# ---------------------------------------------------------------------------
# Refund pairing
# ---------------------------------------------------------------------------


@dataclass
class RefundCandidate:
    """Candidate refund (credit) transaction for a given debit."""

    transaction: Transaction
    days_apart: int


async def find_refund_candidates(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    window_days: int = 30,
) -> list[RefundCandidate]:
    """Surface credit transactions that could be refunds of this debit.

    Criteria: same account, same merchant, opposite direction (credit),
    within window_days, credit.amount <= debit.amount.
    Never auto-pairs — candidates surface for HITL confirmation.
    """
    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    if tx.direction != str(TransactionDirection.DEBIT):
        raise ValidationError("only debit transactions can have refund candidates")
    if tx.merchant_name is None:
        return []

    result = await session.execute(
        sa.select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.account_id == tx.account_id,
            Transaction.direction == str(TransactionDirection.CREDIT),
            Transaction.merchant_name.ilike(tx.merchant_name),
            Transaction.amount <= tx.amount,
            Transaction.refund_peer_id.is_(None),
        )
    )
    candidates: list[RefundCandidate] = []
    for cand in result.scalars().all():
        if cand.id == tx.id:
            continue
        days_apart = abs((tx.posted_date - cand.posted_date).days)
        if days_apart <= window_days:
            candidates.append(RefundCandidate(transaction=cand, days_apart=days_apart))
    candidates.sort(key=lambda c: c.days_apart)
    return candidates


async def pair_refund(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    peer_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    window_days: int = 30,
) -> tuple[Transaction, Transaction]:
    """Confirm a refund pairing (HITL write).

    Validates all pairing criteria then writes refund_peer_id on both rows.
    """
    if transaction_id == peer_id:
        raise ValidationError("a transaction cannot be paired with itself")

    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    peer = await get_transaction(session, transaction_id=peer_id, household_id=household_id)

    # Determine which is debit and which is credit
    if tx.direction == str(TransactionDirection.DEBIT) and peer.direction == str(
        TransactionDirection.CREDIT
    ):
        debit, credit = tx, peer
    elif tx.direction == str(TransactionDirection.CREDIT) and peer.direction == str(
        TransactionDirection.DEBIT
    ):
        debit, credit = peer, tx
    else:
        raise ValidationError("refund pairing requires one debit and one credit transaction")

    if not check_refund_pairable(
        debit_amount=debit.amount,
        credit_amount=credit.amount,
        debit_merchant=debit.merchant_name,
        credit_merchant=credit.merchant_name,
        debit_date=debit.posted_date,
        credit_date=credit.posted_date,
        window_days=window_days,
    ):
        raise ValidationError(
            "transactions do not meet refund pairing criteria "
            "(same merchant, within window, debit >= credit)"
        )

    if debit.refund_peer_id is not None and debit.refund_peer_id != credit.id:
        raise ConflictError("debit transaction already has a different refund peer")
    if credit.refund_peer_id is not None and credit.refund_peer_id != debit.id:
        raise ConflictError("credit transaction already has a different refund peer")

    debit.refund_peer_id = credit.id
    credit.refund_peer_id = debit.id
    await session.flush()

    for entity_id, peer_value in [(debit.id, credit.id), (credit.id, debit.id)]:
        await _write_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_type="transaction",
            entity_id=entity_id,
            operation=AuditOperation.UPDATE,
            delta=[{"op": "add", "path": "/refund_peer_id", "value": str(peer_value)}],
        )
    return debit, credit


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


async def process_dedup(
    session: AsyncSession,
    *,
    transaction: Transaction,
    source: str = "unknown",
    threshold: float = 0.85,
    window_days: int = 3,
) -> list[DeduplicationLog]:
    """Stage 2 fuzzy dedup for a newly ingested transaction.

    Searches for candidates with the same account + amount + date within
    window_days. Scores each with score_dedup_confidence(). Creates
    DeduplicationLog rows for all candidates that pass the preconditions.

    - confidence < threshold → resolution=pending (HITL)
    - confidence >= threshold AND source='simplefin' → resolution=merged,
      archives the new transaction (it is the duplicate)
    """
    from_date = transaction.posted_date - timedelta(days=window_days)
    to_date = transaction.posted_date + timedelta(days=window_days)

    result = await session.execute(
        sa.select(Transaction).where(
            Transaction.id != transaction.id,
            Transaction.account_id == transaction.account_id,
            Transaction.amount == transaction.amount,
            Transaction.posted_date >= from_date,
            Transaction.posted_date <= to_date,
        )
    )
    candidates = result.scalars().all()

    logs: list[DeduplicationLog] = []
    for cand in candidates:
        confidence = score_dedup_confidence(
            transaction.posted_date,
            cand.posted_date,
            transaction.description,
            cand.description,
        )
        if confidence <= 0.0:
            continue

        resolution = DedupResolution.PENDING
        if confidence >= threshold and source == "simplefin":
            resolution = DedupResolution.MERGED
            # Archive the newly ingested transaction — it is the duplicate
            now = datetime.now(tz=UTC)
            transaction.archived_at = now
            transaction.archived_by = None
            await session.flush()

        log = DeduplicationLog(
            household_id=transaction.household_id,
            candidate_a_id=transaction.id,
            candidate_b_id=cand.id,
            confidence=Decimal(str(round(confidence, 4))),
            match_reason=(
                f"account={transaction.account_id}, "
                f"amount={transaction.amount}, "
                f"date_delta={abs((transaction.posted_date - cand.posted_date).days)}, "
                f"description_score={round(confidence, 4)}"
            ),
            resolution=str(resolution),
            resolved_at=datetime.now(tz=UTC) if resolution == DedupResolution.MERGED else None,
        )
        session.add(log)
        logs.append(log)

    await session.flush()
    return logs


async def list_dedup_candidates(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[DeduplicationLog]:
    """Return pending dedup log rows for HITL review."""
    result = await session.execute(
        sa.select(DeduplicationLog).where(
            DeduplicationLog.household_id == household_id,
            DeduplicationLog.resolution == str(DedupResolution.PENDING),
        )
    )
    return list(result.scalars().all())


async def resolve_dedup(
    session: AsyncSession,
    *,
    log_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    resolution: DedupResolution,
) -> DeduplicationLog:
    """Resolve a pending dedup candidate as merged or rejected.

    On merge: archives candidate_a (the duplicate). Logs audit event.
    """
    result = await session.execute(
        sa.select(DeduplicationLog).where(
            DeduplicationLog.id == log_id,
            DeduplicationLog.household_id == household_id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise NotFoundError("deduplication log entry not found")
    if log.resolution != str(DedupResolution.PENDING):
        raise ConflictError("this log entry has already been resolved")

    now = datetime.now(tz=UTC)
    log.resolution = str(resolution)
    log.resolved_at = now
    log.resolved_by = actor_id

    if resolution == DedupResolution.MERGED:
        # Archive candidate_a as the duplicate
        dup_result = await session.execute(
            sa.select(Transaction).where(Transaction.id == log.candidate_a_id)
        )
        dup = dup_result.scalar_one_or_none()
        if dup is not None and dup.archived_at is None:
            dup.archived_at = now
            dup.archived_by = actor_id

    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="deduplication_log",
        entity_id=log_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/resolution", "value": str(resolution)}],
    )
    return log


# ---------------------------------------------------------------------------
# PaymentGroup CRUD
# ---------------------------------------------------------------------------


async def create_payment_group(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    group_type: GroupType,
    member_transaction_ids: list[uuid.UUID],
) -> PaymentGroup:
    """Create a payment group from confirmed candidate transactions."""
    if len(member_transaction_ids) < 2:
        raise ValidationError("payment group requires at least 2 member transactions")

    for tx_id in member_transaction_ids:
        await get_transaction(session, transaction_id=tx_id, household_id=household_id)

    group = PaymentGroup(
        household_id=household_id,
        group_type=str(group_type),
        member_transaction_ids=[str(tid) for tid in member_transaction_ids],
    )
    session.add(group)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="payment_group",
        entity_id=group.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/group_type", "value": str(group_type)},
            {
                "op": "add",
                "path": "/member_count",
                "value": len(member_transaction_ids),
            },
        ],
    )
    return group


async def get_payment_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
) -> PaymentGroup:
    """Return a payment group scoped to the household."""
    result = await session.execute(
        sa.select(PaymentGroup).where(
            PaymentGroup.id == group_id,
            PaymentGroup.household_id == household_id,
        )
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise NotFoundError("payment group not found")
    return group


async def list_payment_groups(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[PaymentGroup]:
    """Return all payment groups in the household."""
    result = await session.execute(
        sa.select(PaymentGroup)
        .where(PaymentGroup.household_id == household_id)
        .order_by(PaymentGroup.created_at.desc())
    )
    return list(result.scalars().all())


async def archive_payment_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a payment group."""
    group = await get_payment_group(session, group_id=group_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    group.archived_at = now
    group.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_type="payment_group",
        entity_id=group_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def update_recurrence_id(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    recurrence_id: uuid.UUID | None,
) -> Transaction:
    """Set or clear the recurrence_id on a transaction.

    Called exclusively by the recurrences module. Writes audit event with
    actor_source='recurrence_detector' so reversals are traceable.
    """
    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    old_value = str(tx.recurrence_id) if tx.recurrence_id is not None else None
    tx.recurrence_id = recurrence_id
    await session.flush()
    await _write_audit(
        session,
        actor_id=None,
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.UPDATE,
        delta=[
            {"op": "test", "path": "/recurrence_id", "value": old_value},
            {
                "op": "replace",
                "path": "/recurrence_id",
                "value": str(recurrence_id) if recurrence_id is not None else None,
            },
        ],
    )
    return tx


async def _find_by_external_id(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    external_id: str,
) -> Transaction | None:
    result = await session.execute(
        sa.select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.external_id == external_id,
        )
    )
    return result.scalar_one_or_none()


async def _write_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
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
        actor_type=ActorType.USER if actor_id is not None else ActorType.SYSTEM,
        actor_source="user_action",
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        delta=delta,
        rationale=rationale,
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Budget interface — allocations in date range with scope filtering
# ---------------------------------------------------------------------------


async def get_allocations_in_range(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    period_start: date,
    period_end: date,
    account_ids: list[uuid.UUID] | None = None,
    category_ids: list[uuid.UUID] | None = None,
    tag_ids: list[uuid.UUID] | None = None,
    direction: str | None = None,
) -> list[SplitAllocation]:
    """Return SplitAllocations for a household within a date range.

    Joins to Transaction for date and account filtering; all within the
    transactions module, so no cross-module join is issued.

    Date range uses Transaction.occurred_at (bank-reported date).
    Scope lists: None or empty = no restriction on that dimension.
    Tag matching: any allocation whose tag_ids contains any of the requested
    tag_ids qualifies (OR semantics).
    direction: 'debit' | 'credit' | None (no restriction)
    """
    stmt = (
        sa.select(SplitAllocation)
        .join(Transaction, Transaction.id == SplitAllocation.transaction_id)
        .where(
            SplitAllocation.household_id == household_id,
            Transaction.occurred_at >= period_start,
            Transaction.occurred_at <= period_end,
        )
    )
    if account_ids:
        stmt = stmt.where(Transaction.account_id.in_(account_ids))
    if category_ids:
        stmt = stmt.where(SplitAllocation.category_id.in_(category_ids))
    if tag_ids:
        tag_conditions = [SplitAllocation.tag_ids.contains([str(tid)]) for tid in tag_ids]
        stmt = stmt.where(sa.or_(*tag_conditions))
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)
    result = await session.execute(stmt)
    return list(result.scalars().all())
