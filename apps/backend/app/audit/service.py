"""Audit service — write, query, and replay audit events.

This module is the ONLY place that creates AuditEvent rows. All other modules
call audit.service.log() rather than constructing AuditEvent directly.

Import constraint: this module must NOT import from any domain module.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

import jsonpatch  # type: ignore[import-untyped]
import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import ActorType, AuditEvent, AuditOperation

_logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cursor encoding
# ---------------------------------------------------------------------------


def _encode_cursor(occurred_at: datetime, event_id: uuid.UUID) -> str:
    payload = json.dumps({"dt": occurred_at.isoformat(), "id": str(event_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["dt"]), uuid.UUID(payload["id"])


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


async def log(
    session: AsyncSession,
    *,
    household_id: uuid.UUID | None,
    actor_type: ActorType,
    actor_source: str,
    entity_type: str,
    entity_id: uuid.UUID,
    operation: AuditOperation,
    delta: list[dict[str, Any]],
    rationale: str | None = None,
    actor_id: uuid.UUID | None = None,
    source_event_id: uuid.UUID | None = None,
) -> AuditEvent | None:
    """Write an audit event within the current session's transaction.

    Uses a savepoint so that a write failure does not invalidate the outer
    transaction. Never raises — failures are emitted to structlog and None is
    returned.
    """
    event = AuditEvent(
        household_id=household_id,
        actor_type=str(actor_type),
        actor_id=actor_id,
        actor_source=actor_source,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=str(operation),
        delta=delta,
        rationale=rationale,
        source_event_id=source_event_id,
    )
    try:
        async with session.begin_nested():
            session.add(event)
    except Exception:
        _logger.exception(
            "audit.write_failed",
            entity_type=entity_type,
            entity_id=str(entity_id),
            operation=str(operation),
        )
        return None
    return event


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


async def get_entity_history(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[AuditEvent]:
    """All events for a specific entity, ordered oldest first."""
    stmt = (
        sa.select(AuditEvent)
        .where(
            AuditEvent.entity_type == entity_type,
            AuditEvent.entity_id == entity_id,
            AuditEvent.household_id == household_id,
        )
        .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_household_log(
    session: AsyncSession,
    household_id: uuid.UUID,
    *,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    operation: AuditOperation | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[AuditEvent], str | None]:
    """Paginated household log, newest first.

    Returns (page, next_cursor). next_cursor is None when no more results.
    """
    stmt = sa.select(AuditEvent).where(AuditEvent.household_id == household_id)

    if from_dt is not None:
        stmt = stmt.where(AuditEvent.occurred_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(AuditEvent.occurred_at <= to_dt)
    if actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if entity_type is not None:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if operation is not None:
        stmt = stmt.where(AuditEvent.operation == str(operation))

    if cursor is not None:
        try:
            cursor_dt, cursor_id = _decode_cursor(cursor)
            stmt = stmt.where(
                sa.or_(
                    AuditEvent.occurred_at < cursor_dt,
                    sa.and_(
                        AuditEvent.occurred_at == cursor_dt,
                        AuditEvent.id < cursor_id,
                    ),
                )
            )
        except Exception:
            _logger.warning("audit.invalid_cursor", cursor=cursor)

    stmt = stmt.order_by(
        AuditEvent.occurred_at.desc(),
        AuditEvent.id.desc(),
    ).limit(limit + 1)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.occurred_at, last.id)

    return rows, next_cursor


# ---------------------------------------------------------------------------
# Replay / reconstruction
# ---------------------------------------------------------------------------


async def reconstruct_state(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    household_id: uuid.UUID,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Apply RFC 6902 patches from the audit log to reconstruct entity state.

    Returns {"state": {...}, "errors": [str, ...]}.
    Best-effort: malformed patches are skipped and noted in errors.
    """
    events = await get_entity_history(session, entity_type, entity_id, household_id)
    if as_of is not None:
        events = [e for e in events if e.occurred_at <= as_of]

    state: dict[str, Any] = {}
    errors: list[str] = []
    for event in events:
        try:
            patch = jsonpatch.JsonPatch(event.delta)  # type: ignore[no-untyped-call]
            state = dict(patch.apply(state))  # type: ignore[no-untyped-call]
        except Exception as exc:
            errors.append(f"event {event.id} ({event.operation}): {exc}")

    return {"state": state, "errors": errors}


async def get_reversal_chain(
    session: AsyncSession,
    source_event_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[AuditEvent]:
    """Return the root event and all reversal events linked via source_event_id.

    Only returns events that belong to the given household.
    Traverses the chain to arbitrary depth. Returns events in chain order
    (root first).
    """
    visited: set[uuid.UUID] = set()
    chain: list[AuditEvent] = []

    root_stmt = sa.select(AuditEvent).where(
        AuditEvent.id == source_event_id,
        AuditEvent.household_id == household_id,
    )
    root_result = await session.execute(root_stmt)
    root = root_result.scalar_one_or_none()
    if root is None:
        return []
    chain.append(root)
    visited.add(root.id)

    current_id = root.id
    while True:
        stmt = sa.select(AuditEvent).where(
            AuditEvent.source_event_id == current_id,
            AuditEvent.id.not_in(visited),
        )
        result = await session.execute(stmt)
        reversals = list(result.scalars().all())
        if not reversals:
            break
        for rev in reversals:
            chain.append(rev)
            visited.add(rev.id)
        current_id = reversals[-1].id

    return chain
