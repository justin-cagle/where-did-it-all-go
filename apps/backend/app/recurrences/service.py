"""Recurrences service layer.

No cross-module DB joins. Transaction data accessed exclusively via
transactions.service public interface. All writes go to recurrences_* tables.

Pure helpers (no DB — safe for Hypothesis tests):
    normalize_merchant
    detect_cadence
    is_amount_within_tolerance
    generate_expected_dates
    apply_exceptions_to_events
    is_instance_missed
"""

import calendar
import re
import string
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.recurrences.enums import (
    AmountStrategy,
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
from app.transactions.enums import TransactionState
from app.transactions.service import (
    get_transaction,
    list_transactions,
)
from app.transactions.service import (
    update_recurrence_id as tx_update_recurrence_id,
)

logger = structlog.get_logger(__name__)

# Number of days tolerance when detecting missed instances and matching dates.
DATE_TOLERANCE_DAYS = 4

# How many months back to scan when detecting recurrences.
_DETECTION_LOOKBACK_MONTHS = 13

# Cadence target days and their tolerance.
_WEEKLY_DAYS = 7
_BIWEEKLY_DAYS = 14
_SEMIMONTHLY_DAYS = 15
_MONTHLY_DAYS = 30
_ANNUAL_DAYS = 365
_INTERVAL_TOLERANCE = 4

_CADENCE_TARGETS: list[tuple[int, Cadence]] = [
    (_WEEKLY_DAYS, Cadence.WEEKLY),
    (_BIWEEKLY_DAYS, Cadence.BIWEEKLY),
    (_SEMIMONTHLY_DAYS, Cadence.SEMIMONTHLY),
    (_MONTHLY_DAYS, Cadence.MONTHLY),
    (_ANNUAL_DAYS, Cadence.ANNUAL),
]

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a uniqueness or state constraint."""


class ValidationError(Exception):
    """Operation violates a domain invariant."""


# ---------------------------------------------------------------------------
# Pure helpers (no DB — safe for Hypothesis tests)
# ---------------------------------------------------------------------------


def normalize_merchant(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Deterministic. Used for grouping transactions by merchant in detection.
    """
    n = name.lower()
    n = n.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", n).strip()


def detect_cadence(dates: list[date]) -> Cadence | None:
    """Identify consistent interval pattern in >= 3 dates.

    Returns the matched Cadence or None if no consistent pattern found.
    Checks cadences in order: weekly, biweekly, semimonthly, monthly, annual.
    First match wins (resolves ambiguity at boundaries).
    """
    if len(dates) < 3:
        return None
    sorted_dates = sorted(dates)
    deltas = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]
    for target, cadence in _CADENCE_TARGETS:
        if all(abs(d - target) <= _INTERVAL_TOLERANCE for d in deltas):
            return cadence
    return None


def is_amount_within_tolerance(
    amount: Decimal,
    expected: Decimal,
    tolerance: Decimal,
) -> bool:
    """Return True if |amount - expected| <= tolerance."""
    return abs(amount - expected) <= tolerance


def generate_expected_dates(
    *,
    cadence: str,
    start_date: date,
    end_date: date | None,
    expected_day_of_period: int | None,
    from_date: date,
    to_date: date,
) -> list[date]:
    """Generate all expected occurrence dates within [from_date, to_date].

    Respects start_date and end_date. custom_cron treated as monthly.
    Pure — takes primitives, not model objects.
    """
    cap = min(end_date, to_date) if end_date else to_date
    results: list[date] = []

    if cadence == str(Cadence.WEEKLY):
        d = start_date
        while d <= cap:
            if d >= from_date:
                results.append(d)
            d += timedelta(days=_WEEKLY_DAYS)

    elif cadence == str(Cadence.BIWEEKLY):
        d = start_date
        while d <= cap:
            if d >= from_date:
                results.append(d)
            d += timedelta(days=_BIWEEKLY_DAYS)

    elif cadence == str(Cadence.SEMIMONTHLY):
        base_day = expected_day_of_period or start_date.day
        year, month = start_date.year, start_date.month
        while date(year, month, 1) <= cap:
            max_day = calendar.monthrange(year, month)[1]
            d1 = date(year, month, min(base_day, max_day))
            second_day = min(base_day + 15, max_day)
            d2 = date(year, month, second_day)
            for d in (d1, d2):
                if from_date <= d <= cap:
                    results.append(d)
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1

    elif cadence in (str(Cadence.MONTHLY), str(Cadence.CUSTOM_CRON)):
        target_day = expected_day_of_period or start_date.day
        year, month = start_date.year, start_date.month
        while True:
            max_day = calendar.monthrange(year, month)[1]
            d = date(year, month, min(target_day, max_day))
            if d > cap:
                break
            if d >= from_date:
                results.append(d)
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1

    elif cadence == str(Cadence.ANNUAL):
        year = start_date.year
        target_month = start_date.month
        target_day = expected_day_of_period or start_date.day
        while True:
            max_day = calendar.monthrange(year, target_month)[1]
            d = date(year, target_month, min(target_day, max_day))
            if d > cap:
                break
            if d >= from_date:
                results.append(d)
            year += 1

    return sorted(results)


@dataclass
class ExpectedEvent:
    """An expected recurrence instance in a given date window."""

    recurrence_id: uuid.UUID
    account_id: uuid.UUID
    expected_date: date
    expected_amount: Decimal
    currency: str
    cadence: str
    merchant_name: str | None
    exception_type: str | None = None
    override_amount: Decimal | None = None
    override_date: date | None = None


def apply_exceptions_to_events(
    events: list[ExpectedEvent],
    exceptions: list[RecurrenceException],
) -> list[ExpectedEvent]:
    """Apply a list of RecurrenceExceptions to the raw expected event list.

    Pure — no side effects. Returns a new list.
    - SKIP: removes the matching instance entirely.
    - AMOUNT_CHANGE: replaces expected_amount.
    - DATE_SHIFT: moves expected_date to override_date.
    """
    exc_by_period: dict[date, RecurrenceException] = {e.affected_period: e for e in exceptions}
    result: list[ExpectedEvent] = []
    for ev in events:
        exc = exc_by_period.get(ev.expected_date)
        if exc is None:
            result.append(ev)
        elif exc.exception_type == str(ExceptionType.SKIP):
            pass  # instance removed
        elif exc.exception_type == str(ExceptionType.AMOUNT_CHANGE):
            new_amount = (
                exc.override_amount if exc.override_amount is not None else ev.expected_amount
            )
            result.append(
                replace(
                    ev,
                    expected_amount=new_amount,
                    exception_type=exc.exception_type,
                    override_amount=exc.override_amount,
                )
            )
        elif exc.exception_type == str(ExceptionType.DATE_SHIFT):
            new_date = exc.override_date if exc.override_date is not None else ev.expected_date
            result.append(
                replace(
                    ev,
                    expected_date=new_date,
                    exception_type=exc.exception_type,
                    override_date=exc.override_date,
                )
            )
        else:
            result.append(ev)
    return result


def is_instance_missed(
    expected_date: date,
    today: date,
    date_tolerance_days: int = DATE_TOLERANCE_DAYS,
) -> bool:
    """Return True iff the expected date has passed the tolerance window with no match."""
    return today > expected_date + timedelta(days=date_tolerance_days)


# ---------------------------------------------------------------------------
# Recurrence CRUD
# ---------------------------------------------------------------------------


async def create_recurrence(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    kind: RecurrenceKind,
    cadence: Cadence,
    expected_amount: Decimal,
    currency: str,
    tolerance: Decimal = Decimal("0"),
    expected_day_of_period: int | None = None,
    expected_amount_strategy: AmountStrategy = AmountStrategy.FIXED,
    linked_category_id: uuid.UUID | None = None,
    linked_account_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    merchant_name: str | None = None,
    recurrence_metadata: dict[str, Any] | None = None,
) -> Recurrence:
    """Create a declared recurrence."""
    rec = Recurrence(
        household_id=household_id,
        account_id=account_id,
        kind=str(kind),
        cadence=str(cadence),
        expected_amount=expected_amount,
        currency=currency.upper(),
        tolerance=tolerance,
        expected_day_of_period=expected_day_of_period,
        expected_amount_strategy=str(expected_amount_strategy),
        linked_category_id=linked_category_id,
        linked_account_id=linked_account_id,
        start_date=start_date or date.today(),
        end_date=end_date,
        merchant_name=merchant_name,
        recurrence_metadata=recurrence_metadata or {},
    )
    session.add(rec)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence",
        entity_id=rec.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/kind", "value": str(kind)},
            {"op": "add", "path": "/cadence", "value": str(cadence)},
            {"op": "add", "path": "/expected_amount", "value": str(expected_amount)},
        ],
    )
    return rec


async def get_recurrence(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
) -> Recurrence:
    """Return a recurrence scoped to the household. Raises NotFoundError if absent."""
    result = await session.execute(
        sa.select(Recurrence).where(
            Recurrence.id == recurrence_id,
            Recurrence.household_id == household_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise NotFoundError("recurrence not found")
    return rec


async def list_recurrences(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
) -> list[Recurrence]:
    """Return active recurrences for the household."""
    stmt = sa.select(Recurrence).where(Recurrence.household_id == household_id)
    if account_id is not None:
        stmt = stmt.where(Recurrence.account_id == account_id)
    stmt = stmt.order_by(Recurrence.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_recurrence(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    cadence: Cadence | None = None,
    expected_amount: Decimal | None = None,
    currency: str | None = None,
    tolerance: Decimal | None = None,
    expected_day_of_period: int | None = None,
    expected_amount_strategy: AmountStrategy | None = None,
    linked_category_id: uuid.UUID | None = None,
    linked_account_id: uuid.UUID | None = None,
    end_date: date | None = None,
    merchant_name: str | None = None,
    recurrence_metadata: dict[str, Any] | None = None,
) -> Recurrence:
    """Update mutable fields of a recurrence."""
    rec = await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    if cadence is not None:
        delta.append({"op": "replace", "path": "/cadence", "value": str(cadence)})
        rec.cadence = str(cadence)
    if expected_amount is not None:
        delta.append({"op": "replace", "path": "/expected_amount", "value": str(expected_amount)})
        rec.expected_amount = expected_amount
    if currency is not None:
        delta.append({"op": "replace", "path": "/currency", "value": currency.upper()})
        rec.currency = currency.upper()
    if tolerance is not None:
        delta.append({"op": "replace", "path": "/tolerance", "value": str(tolerance)})
        rec.tolerance = tolerance
    if expected_day_of_period is not None:
        rec.expected_day_of_period = expected_day_of_period
    if expected_amount_strategy is not None:
        rec.expected_amount_strategy = str(expected_amount_strategy)
    if linked_category_id is not None:
        rec.linked_category_id = linked_category_id
    if linked_account_id is not None:
        rec.linked_account_id = linked_account_id
    if end_date is not None:
        rec.end_date = end_date
    if merchant_name is not None:
        rec.merchant_name = merchant_name
    if recurrence_metadata is not None:
        rec.recurrence_metadata = recurrence_metadata

    if delta:
        await session.flush()
        await _write_audit(
            session,
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="recurrence",
            entity_id=recurrence_id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return rec


async def archive_recurrence(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a recurrence. Never hard-deletes."""
    rec = await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    rec.archived_at = now
    rec.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence",
        entity_id=recurrence_id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


async def pause_recurrence(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Recurrence:
    """Pause missed-detection alerts for a recurrence."""
    rec = await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    if rec.paused:
        raise ConflictError("recurrence is already paused")
    rec.paused = True
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence",
        entity_id=recurrence_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/paused", "value": True}],
    )
    return rec


async def resume_recurrence(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Recurrence:
    """Resume missed-detection alerts for a paused recurrence."""
    rec = await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    if not rec.paused:
        raise ConflictError("recurrence is not paused")
    rec.paused = False
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence",
        entity_id=recurrence_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/paused", "value": False}],
    )
    return rec


# ---------------------------------------------------------------------------
# Recurrence detection
# ---------------------------------------------------------------------------


async def detect_recurrences(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[RecurrenceCandidate]:
    """Mine last 13 months of posted transactions for recurring patterns.

    Groups by (account_id, normalized_merchant_name, amount) — exact amount
    match for v1. Requires >= 3 occurrences with a consistent interval.
    Writes RecurrenceCandidate rows (status=pending).

    Idempotent: skips groups that already have a pending or confirmed candidate.
    NEVER creates Recurrence rows — that always requires HITL confirmation.
    """
    lookback_start = date.today() - timedelta(days=_DETECTION_LOOKBACK_MONTHS * 30)
    txs = await list_transactions(
        session,
        household_id=household_id,
        state=TransactionState.POSTED,
        date_from=lookback_start,
    )

    # Group by (account_id, normalized_merchant_name, amount, currency)
    groups: dict[tuple[uuid.UUID, str, Decimal, str], list[Any]] = {}
    for tx in txs:
        if tx.merchant_name is None:
            continue
        key = (tx.account_id, normalize_merchant(tx.merchant_name), tx.amount, tx.currency)
        groups.setdefault(key, []).append(tx)

    # Load existing candidates to skip duplicates
    existing_result = await session.execute(
        sa.select(RecurrenceCandidate).where(
            RecurrenceCandidate.household_id == household_id,
            RecurrenceCandidate.status.in_(
                [str(CandidateStatus.PENDING), str(CandidateStatus.CONFIRMED)]
            ),
        )
    )
    existing: set[tuple[uuid.UUID, str, Decimal]] = {
        (c.account_id, normalize_merchant(c.merchant_name), c.expected_amount)
        for c in existing_result.scalars().all()
    }

    new_candidates: list[RecurrenceCandidate] = []
    now = datetime.now(tz=UTC)

    for (account_id, norm_merchant, amount, currency), group_txs in groups.items():
        if len(group_txs) < 3:
            continue

        dates = [tx.posted_date for tx in group_txs]
        cadence = detect_cadence(dates)
        if cadence is None:
            continue

        if (account_id, norm_merchant, amount) in existing:
            continue

        raw_merchant = group_txs[0].merchant_name or norm_merchant
        sample_ids = [str(tx.id) for tx in sorted(group_txs, key=lambda t: t.posted_date)[:5]]

        candidate = RecurrenceCandidate(
            household_id=household_id,
            account_id=account_id,
            merchant_name=raw_merchant,
            cadence=str(cadence),
            expected_amount=amount,
            currency=currency,
            sample_transaction_ids=sample_ids,
            occurrence_count=len(group_txs),
            status=str(CandidateStatus.PENDING),
            detected_at=now,
        )
        session.add(candidate)
        new_candidates.append(candidate)

    if new_candidates:
        await session.flush()
    logger.info(
        "detect_recurrences.complete",
        household_id=str(household_id),
        new_candidates=len(new_candidates),
    )
    return new_candidates


async def confirm_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Recurrence:
    """Promote a RecurrenceCandidate to a confirmed Recurrence (HITL write).

    Back-fills recurrence_id on matching historical transactions and writes
    RecurrenceMatch rows for each match.
    """
    result = await session.execute(
        sa.select(RecurrenceCandidate).where(
            RecurrenceCandidate.id == candidate_id,
            RecurrenceCandidate.household_id == household_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise NotFoundError("candidate not found")
    if candidate.status != str(CandidateStatus.PENDING):
        raise ConflictError(
            f"candidate status is {candidate.status!r}; only pending candidates can be confirmed"
        )

    # Create the Recurrence
    rec = Recurrence(
        household_id=household_id,
        account_id=candidate.account_id,
        kind=str(RecurrenceKind.DETECTED),
        cadence=candidate.cadence,
        expected_amount=candidate.expected_amount,
        currency=candidate.currency,
        tolerance=Decimal("0"),
        start_date=date.today(),
        merchant_name=candidate.merchant_name,
    )
    session.add(rec)
    await session.flush()

    # Back-fill matching historical transactions
    historical = await list_transactions(
        session,
        household_id=household_id,
        account_id=candidate.account_id,
        state=TransactionState.POSTED,
    )
    matched_at = datetime.now(tz=UTC)
    for tx in historical:
        if tx.merchant_name is None:
            continue
        if normalize_merchant(tx.merchant_name) != normalize_merchant(candidate.merchant_name):
            continue
        if not is_amount_within_tolerance(tx.amount, candidate.expected_amount, Decimal("0")):
            continue

        await tx_update_recurrence_id(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            recurrence_id=rec.id,
        )
        match = RecurrenceMatch(
            recurrence_id=rec.id,
            transaction_id=tx.id,
            matched_at=matched_at,
            status=str(MatchStatus.MATCHED),
        )
        session.add(match)

    candidate.status = str(CandidateStatus.CONFIRMED)
    candidate.recurrence_id = rec.id
    await session.flush()

    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence_candidate",
        entity_id=candidate_id,
        operation=AuditOperation.ACCEPT,
        delta=[
            {"op": "replace", "path": "/status", "value": "confirmed"},
            {"op": "add", "path": "/recurrence_id", "value": str(rec.id)},
        ],
    )
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence",
        entity_id=rec.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/kind", "value": "detected"},
            {"op": "add", "path": "/cadence", "value": candidate.cadence},
            {"op": "add", "path": "/source_candidate_id", "value": str(candidate_id)},
        ],
    )
    return rec


async def dismiss_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> RecurrenceCandidate:
    """Mark a candidate as dismissed (user rejected it)."""
    result = await session.execute(
        sa.select(RecurrenceCandidate).where(
            RecurrenceCandidate.id == candidate_id,
            RecurrenceCandidate.household_id == household_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise NotFoundError("candidate not found")
    if candidate.status != str(CandidateStatus.PENDING):
        raise ConflictError(
            f"candidate status is {candidate.status!r}; only pending candidates can be dismissed"
        )

    candidate.status = str(CandidateStatus.DISMISSED)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence_candidate",
        entity_id=candidate_id,
        operation=AuditOperation.REJECT,
        delta=[{"op": "replace", "path": "/status", "value": "dismissed"}],
    )
    return candidate


async def list_candidates(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    status: CandidateStatus | None = CandidateStatus.PENDING,
) -> list[RecurrenceCandidate]:
    """Return candidates for the household, optionally filtered by status."""
    stmt = sa.select(RecurrenceCandidate).where(RecurrenceCandidate.household_id == household_id)
    if status is not None:
        stmt = stmt.where(RecurrenceCandidate.status == str(status))
    stmt = stmt.order_by(RecurrenceCandidate.detected_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Transaction matching
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    """Result of matching a single transaction against recurrences."""

    matched: bool
    recurrence_id: uuid.UUID | None
    status: MatchStatus | None
    deviation_amount: Decimal | None
    deviation_days: int | None


async def match_transaction(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
) -> MatchResult:
    """Attempt to match a transaction against active recurrences.

    Idempotent: skips if the transaction already has a RecurrenceMatch.
    If matched: writes RecurrenceMatch, updates transaction.recurrence_id.
    Deviation (amount or date beyond tolerance): writes deviated match.
    """
    # Skip if already matched
    existing_match = await session.execute(
        sa.select(RecurrenceMatch).where(
            RecurrenceMatch.transaction_id == transaction_id,
            RecurrenceMatch.status.in_([str(MatchStatus.MATCHED), str(MatchStatus.DEVIATED)]),
        )
    )
    if existing_match.scalar_one_or_none() is not None:
        return MatchResult(
            matched=True,
            recurrence_id=None,
            status=None,
            deviation_amount=None,
            deviation_days=None,
        )

    tx = await get_transaction(session, transaction_id=transaction_id, household_id=household_id)
    if tx.merchant_name is None:
        return MatchResult(
            matched=False,
            recurrence_id=None,
            status=None,
            deviation_amount=None,
            deviation_days=None,
        )

    norm = normalize_merchant(tx.merchant_name)

    # Load active recurrences for this account
    rec_result = await session.execute(
        sa.select(Recurrence).where(
            Recurrence.household_id == household_id,
            Recurrence.account_id == tx.account_id,
            Recurrence.paused.is_(False),
        )
    )
    recurrences = list(rec_result.scalars().all())

    matched_at = datetime.now(tz=UTC)
    for rec in recurrences:
        if rec.merchant_name is None:
            continue
        if normalize_merchant(rec.merchant_name) != norm:
            continue
        if not is_amount_within_tolerance(tx.amount, rec.expected_amount, rec.tolerance):
            continue

        # Compute expected date for the transaction's period
        expected_dates = generate_expected_dates(
            cadence=rec.cadence,
            start_date=rec.start_date,
            end_date=rec.end_date,
            expected_day_of_period=rec.expected_day_of_period,
            from_date=tx.posted_date - timedelta(days=DATE_TOLERANCE_DAYS * 3),
            to_date=tx.posted_date + timedelta(days=DATE_TOLERANCE_DAYS * 3),
        )
        nearest_expected = min(
            expected_dates,
            key=lambda d: abs((d - tx.posted_date).days),
            default=None,
        )

        dev_amount = tx.amount - rec.expected_amount
        dev_days = (tx.posted_date - nearest_expected).days if nearest_expected else None

        amount_deviated = abs(dev_amount) > rec.tolerance
        date_deviated = dev_days is not None and abs(dev_days) > DATE_TOLERANCE_DAYS
        match_status = (
            MatchStatus.DEVIATED if (amount_deviated or date_deviated) else MatchStatus.MATCHED
        )

        match = RecurrenceMatch(
            recurrence_id=rec.id,
            transaction_id=tx.id,
            matched_at=matched_at,
            status=str(match_status),
            deviation_amount=dev_amount if amount_deviated else None,
            deviation_days=dev_days,
            expected_date=nearest_expected,
        )
        session.add(match)
        await session.flush()

        await tx_update_recurrence_id(
            session,
            transaction_id=tx.id,
            household_id=household_id,
            recurrence_id=rec.id,
        )

        logger.info(
            "match_transaction.matched",
            transaction_id=str(tx.id),
            recurrence_id=str(rec.id),
            status=str(match_status),
        )
        return MatchResult(
            matched=True,
            recurrence_id=rec.id,
            status=match_status,
            deviation_amount=dev_amount if amount_deviated else None,
            deviation_days=dev_days,
        )

    return MatchResult(
        matched=False, recurrence_id=None, status=None, deviation_amount=None, deviation_days=None
    )


# ---------------------------------------------------------------------------
# Missed detection
# ---------------------------------------------------------------------------


async def check_missed(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[RecurrenceMatch]:
    """Write RecurrenceMatch(status=missed) for overdue expected instances.

    Checks the most recent expected periods for each active non-paused recurrence.
    Idempotent: skips periods that already have a match or missed record.
    """
    today = date.today()
    recs = await list_recurrences(session, household_id=household_id)
    new_misses: list[RecurrenceMatch] = []

    for rec in recs:
        if rec.paused:
            continue

        # Check the last few expected dates
        check_from = today - timedelta(days=60)
        expected_dates = generate_expected_dates(
            cadence=rec.cadence,
            start_date=rec.start_date,
            end_date=rec.end_date,
            expected_day_of_period=rec.expected_day_of_period,
            from_date=check_from,
            to_date=today,
        )

        for exp_date in expected_dates:
            if not is_instance_missed(exp_date, today):
                continue

            # Check for existing match near this date
            existing_result = await session.execute(
                sa.select(RecurrenceMatch).where(
                    RecurrenceMatch.recurrence_id == rec.id,
                    RecurrenceMatch.expected_date == exp_date,
                )
            )
            if existing_result.scalar_one_or_none() is not None:
                continue

            miss = RecurrenceMatch(
                recurrence_id=rec.id,
                transaction_id=None,
                matched_at=datetime.now(tz=UTC),
                status=str(MatchStatus.MISSED),
                expected_date=exp_date,
            )
            session.add(miss)
            new_misses.append(miss)

    if new_misses:
        await session.flush()
    logger.info(
        "check_missed.complete",
        household_id=str(household_id),
        new_misses=len(new_misses),
    )
    return new_misses


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


async def apply_exception(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    exception_type: ExceptionType,
    affected_period: date,
    override_amount: Decimal | None = None,
    override_date: date | None = None,
    note: str | None = None,
) -> RecurrenceException:
    """Write a single-instance override on a recurrence."""
    await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)

    if exception_type == ExceptionType.AMOUNT_CHANGE and override_amount is None:
        raise ValidationError("override_amount required for amount_change exception")
    if exception_type == ExceptionType.DATE_SHIFT and override_date is None:
        raise ValidationError("override_date required for date_shift exception")

    exc = RecurrenceException(
        recurrence_id=recurrence_id,
        exception_type=str(exception_type),
        affected_period=affected_period,
        override_amount=override_amount,
        override_date=override_date,
        note=note,
    )
    session.add(exc)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="recurrence_exception",
        entity_id=exc.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/exception_type", "value": str(exception_type)},
            {"op": "add", "path": "/affected_period", "value": str(affected_period)},
        ],
    )
    return exc


async def list_exceptions(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[RecurrenceException]:
    """Return all exceptions for a recurrence."""
    await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    result = await session.execute(
        sa.select(RecurrenceException)
        .where(RecurrenceException.recurrence_id == recurrence_id)
        .order_by(RecurrenceException.affected_period)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


async def list_matches(
    session: AsyncSession,
    *,
    recurrence_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[RecurrenceMatch]:
    """Return match history for a recurrence."""
    await get_recurrence(session, recurrence_id=recurrence_id, household_id=household_id)
    result = await session.execute(
        sa.select(RecurrenceMatch)
        .where(RecurrenceMatch.recurrence_id == recurrence_id)
        .order_by(RecurrenceMatch.matched_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Expected events (projections / calendar)
# ---------------------------------------------------------------------------


async def get_expected_events(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> list[ExpectedEvent]:
    """Return expected recurrence instances in a date window, after applying exceptions.

    Used by the projections engine and calendar. Returns events in date order.
    """
    recs = await list_recurrences(session, household_id=household_id)
    all_events: list[ExpectedEvent] = []

    for rec in recs:
        dates = generate_expected_dates(
            cadence=rec.cadence,
            start_date=rec.start_date,
            end_date=rec.end_date,
            expected_day_of_period=rec.expected_day_of_period,
            from_date=from_date,
            to_date=to_date,
        )
        raw_events = [
            ExpectedEvent(
                recurrence_id=rec.id,
                account_id=rec.account_id,
                expected_date=d,
                expected_amount=rec.expected_amount,
                currency=rec.currency,
                cadence=rec.cadence,
                merchant_name=rec.merchant_name,
            )
            for d in dates
        ]

        exc_result = await session.execute(
            sa.select(RecurrenceException).where(
                RecurrenceException.recurrence_id == rec.id,
                RecurrenceException.affected_period.between(from_date, to_date),
            )
        )
        exceptions = list(exc_result.scalars().all())
        adjusted = apply_exceptions_to_events(raw_events, exceptions)
        all_events.extend(adjusted)

    all_events.sort(key=lambda e: e.expected_date)
    return all_events


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _write_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    actor_source: str,
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
        actor_source=actor_source,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        delta=delta,
        rationale=rationale,
        actor_id=actor_id,
    )
