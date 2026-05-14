"""Tests for the audit module.

Coverage targets:
  - audit.service: 85%+ line coverage
  - DB-level append-only invariant (integration, requires @pytest.mark.integration)
  - reconstruct_state correctness (Hypothesis property test)
  - log() never raises (mocked DB failure)
  - Cursor pagination completeness (Hypothesis property test)
  - Reversal chain traversal
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.audit import service as audit_service
from app.audit.models import ActorType, AuditEvent, AuditOperation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    *,
    occurred_at: datetime | None = None,
    entity_type: str = "test_entity",
    entity_id: uuid.UUID | None = None,
    household_id: uuid.UUID | None = None,
    operation: str = "create",
    delta: list[Any] | None = None,
    source_event_id: uuid.UUID | None = None,
) -> AuditEvent:
    eid = entity_id or uuid.uuid4()
    hid = household_id or uuid.uuid4()
    event = AuditEvent(
        actor_type="system",
        actor_id=None,
        actor_source="test",
        household_id=hid,
        entity_type=entity_type,
        entity_id=eid,
        operation=operation,
        delta=delta or [],
        rationale=None,
        source_event_id=source_event_id,
    )
    event.occurred_at = occurred_at or datetime.now(tz=UTC)
    return event


# ---------------------------------------------------------------------------
# Unit — log() never raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_never_raises_on_db_failure() -> None:
    """log() catches DB errors and returns None without propagating."""
    session = MagicMock()
    session.begin_nested = MagicMock()
    nested_ctx = AsyncMock()
    nested_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB unavailable"))
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested.return_value = nested_ctx

    result = await audit_service.log(
        session,
        household_id=uuid.uuid4(),
        actor_type=ActorType.SYSTEM,
        actor_source="test",
        entity_type="test",
        entity_id=uuid.uuid4(),
        operation=AuditOperation.CREATE,
        delta=[],
    )
    assert result is None


@pytest.mark.asyncio
async def test_log_returns_event_on_success() -> None:
    """log() returns AuditEvent on successful write."""
    session = MagicMock()
    nested_ctx = AsyncMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)
    session.add = MagicMock()

    entity_id = uuid.uuid4()
    result = await audit_service.log(
        session,
        household_id=uuid.uuid4(),
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="account",
        entity_id=entity_id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": "checking"}],
        actor_id=uuid.uuid4(),
    )
    assert result is not None
    assert result.entity_id == entity_id
    assert result.operation == "create"


@pytest.mark.asyncio
async def test_log_never_raises_on_any_exception() -> None:
    """log() swallows all exception types."""
    session = MagicMock()
    session.begin_nested = MagicMock(side_effect=RuntimeError("connection lost"))

    result = await audit_service.log(
        session,
        household_id=None,
        actor_type=ActorType.SYSTEM,
        actor_source="test",
        entity_type="import_job",
        entity_id=uuid.uuid4(),
        operation=AuditOperation.CREATE,
        delta=[],
    )
    assert result is None


# ---------------------------------------------------------------------------
# Unit — cursor encoding round-trip
# ---------------------------------------------------------------------------


def test_cursor_round_trip() -> None:
    now = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
    event_id = uuid.uuid4()
    cursor = audit_service._encode_cursor(now, event_id)
    decoded_dt, decoded_id = audit_service._decode_cursor(cursor)
    assert decoded_dt == now
    assert decoded_id == event_id


# ---------------------------------------------------------------------------
# Property — reconstruct_state applies patches in order
# ---------------------------------------------------------------------------


def _valid_patch_sequence(
    n: int,
) -> list[list[dict[str, Any]]]:
    """Generate n sequential patches that build a valid state from {}."""
    patches: list[list[dict[str, Any]]] = []
    keys: set[str] = set()
    for _ in range(n):
        if not keys:
            # Must add at least one key first
            key = "/key0"
            keys.add(key)
            patches.append([{"op": "add", "path": key, "value": "v0"}])
        else:
            key = next(iter(keys))
            patches.append([{"op": "replace", "path": key, "value": "updated"}])
    return patches


@pytest.mark.asyncio
@given(n=st.integers(min_value=1, max_value=20))
@settings(max_examples=50)
async def test_reconstruct_state_applies_patches_in_order(n: int) -> None:
    """reconstruct_state applies N valid RFC 6902 patches in sequence."""
    import jsonpatch

    patch_sequence = _valid_patch_sequence(n)

    session = AsyncMock()
    entity_id = uuid.uuid4()
    household_id = uuid.uuid4()

    events: list[AuditEvent] = []
    for i, delta in enumerate(patch_sequence):
        e = _make_event(
            occurred_at=datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC),
            entity_id=entity_id,
            household_id=household_id,
            delta=delta,
        )
        # Simulate UUIDv7 with incrementing ids
        e.id = uuid.UUID(int=i + 1)
        events.append(e)

    with patch.object(audit_service, "get_entity_history", return_value=events):
        result = await audit_service.reconstruct_state(
            session, "test_entity", entity_id, household_id
        )

    # Apply expected final state manually
    expected: dict[str, Any] = {}
    for delta in patch_sequence:
        expected = jsonpatch.apply_patch(expected, delta)

    assert result["state"] == expected
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_reconstruct_state_handles_malformed_patch() -> None:
    """Malformed patches are skipped; errors collected; state partially reconstructed."""
    session = AsyncMock()
    entity_id = uuid.uuid4()
    household_id = uuid.uuid4()

    good = _make_event(
        occurred_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        entity_id=entity_id,
        household_id=household_id,
        delta=[{"op": "add", "path": "/name", "value": "test"}],
    )
    good.id = uuid.UUID(int=1)

    bad = _make_event(
        occurred_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        entity_id=entity_id,
        household_id=household_id,
        delta=[{"op": "replace", "path": "/nonexistent", "value": "x"}],
    )
    bad.id = uuid.UUID(int=2)

    with patch.object(audit_service, "get_entity_history", return_value=[good, bad]):
        result = await audit_service.reconstruct_state(
            session, "test_entity", entity_id, household_id
        )

    assert result["state"] == {"name": "test"}
    assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Property — cursor pagination: all events returned exactly once, no gaps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(num_events=st.integers(min_value=0, max_value=30))
@settings(max_examples=50)
async def test_cursor_pagination_completeness(num_events: int) -> None:
    """Paginating with limit=1 returns all events exactly once."""
    household_id = uuid.uuid4()
    all_events = [
        _make_event(
            occurred_at=datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC),
            household_id=household_id,
        )
        for i in range(num_events)
    ]
    # Assign unique ids
    for i, e in enumerate(all_events):
        e.id = uuid.UUID(int=i + 1)

    # Sort as DB would (newest first)
    sorted_events = sorted(all_events, key=lambda e: (e.occurred_at, e.id), reverse=True)

    async def _mock_get_log(
        session: Any,
        hid: uuid.UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
        **kwargs: Any,
    ) -> tuple[list[AuditEvent], str | None]:
        if cursor is None:
            idx = 0
        else:
            dt, cid = audit_service._decode_cursor(cursor)
            idx = next(
                (
                    i
                    for i, e in enumerate(sorted_events)
                    if e.occurred_at < dt or (e.occurred_at == dt and e.id < cid)
                ),
                len(sorted_events),
            )
        page = sorted_events[idx : idx + limit]
        remaining = sorted_events[idx + limit :]
        if remaining:
            last = page[-1]
            next_cursor = audit_service._encode_cursor(last.occurred_at, last.id)
        else:
            next_cursor = None
        return page, next_cursor

    session = AsyncMock()
    collected: list[AuditEvent] = []
    cursor: str | None = None
    iterations = 0

    while True:
        page, cursor = await _mock_get_log(session, household_id, limit=1, cursor=cursor)
        collected.extend(page)
        iterations += 1
        if cursor is None:
            break
        if iterations > num_events + 5:
            pytest.fail("Pagination did not terminate")

    assert len(collected) == num_events
    collected_ids = [e.id for e in collected]
    assert len(collected_ids) == len(set(collected_ids)), "Duplicates found"


# ---------------------------------------------------------------------------
# Unit — reversal chain traversal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reversal_chain_returns_root_and_reversals() -> None:
    """get_reversal_chain returns root + chained reversal events."""
    root_id = uuid.UUID(int=1)
    rev1_id = uuid.UUID(int=2)
    rev2_id = uuid.UUID(int=3)
    household_id = uuid.uuid4()

    root = _make_event(household_id=household_id)
    root.id = root_id
    root.source_event_id = None

    rev1 = _make_event(household_id=household_id, source_event_id=root_id)
    rev1.id = rev1_id

    rev2 = _make_event(household_id=household_id, source_event_id=rev1_id)
    rev2.id = rev2_id

    call_count = 0

    async def _mock_execute(stmt: Any) -> Any:
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = root
        elif call_count == 2:
            mock_result.scalars.return_value.all.return_value = [rev1]
        elif call_count == 3:
            mock_result.scalars.return_value.all.return_value = [rev2]
        else:
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_mock_execute)

    chain = await audit_service.get_reversal_chain(session, root_id, household_id)
    assert [e.id for e in chain] == [root_id, rev1_id, rev2_id]


@pytest.mark.asyncio
async def test_get_reversal_chain_missing_root_returns_empty() -> None:
    session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    chain = await audit_service.get_reversal_chain(session, uuid.uuid4(), uuid.uuid4())
    assert chain == []


# ---------------------------------------------------------------------------
# Integration — DB-level append-only enforcement (real Postgres)
# ---------------------------------------------------------------------------


async def _install_immutability_triggers(session: Any) -> None:
    """Create append-only triggers on audit_event (migration 0013 not run in test DB)."""
    import sqlalchemy as sa

    await session.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION audit_event_immutable()
            RETURNS TRIGGER LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'audit_event rows are immutable'
                    USING ERRCODE = 'restrict_violation';
            END;
            $$;
            """
        )
    )
    await session.execute(sa.text("DROP TRIGGER IF EXISTS audit_event_no_update ON audit_event"))
    await session.execute(
        sa.text(
            """
            CREATE TRIGGER audit_event_no_update
                BEFORE UPDATE ON audit_event
                FOR EACH ROW EXECUTE FUNCTION audit_event_immutable()
            """
        )
    )
    await session.execute(sa.text("DROP TRIGGER IF EXISTS audit_event_no_delete ON audit_event"))
    await session.execute(
        sa.text(
            """
            CREATE TRIGGER audit_event_no_delete
                BEFORE DELETE ON audit_event
                FOR EACH ROW EXECUTE FUNCTION audit_event_immutable()
            """
        )
    )
    await session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_event_update_raises_db_error(db_session: Any) -> None:
    """Trigger prevents UPDATE on audit_event — DB raises exception."""
    import sqlalchemy as sa

    await _install_immutability_triggers(db_session)

    entity_id = uuid.uuid4()
    household_id = uuid.uuid4()
    event = await audit_service.log(
        db_session,
        household_id=household_id,
        actor_type=ActorType.SYSTEM,
        actor_source="test",
        entity_type="test",
        entity_id=entity_id,
        operation=AuditOperation.CREATE,
        delta=[],
    )
    assert event is not None
    await db_session.flush()

    with pytest.raises(Exception, match="immutable"):
        await db_session.execute(
            sa.text("UPDATE audit_event SET actor_source = 'tampered' WHERE id = :id").bindparams(
                id=event.id
            )
        )
        await db_session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_event_delete_raises_db_error(db_session: Any) -> None:
    """Trigger prevents DELETE on audit_event — DB raises exception."""
    import sqlalchemy as sa

    await _install_immutability_triggers(db_session)

    entity_id = uuid.uuid4()
    household_id = uuid.uuid4()
    event = await audit_service.log(
        db_session,
        household_id=household_id,
        actor_type=ActorType.SYSTEM,
        actor_source="test",
        entity_type="test",
        entity_id=entity_id,
        operation=AuditOperation.CREATE,
        delta=[],
    )
    assert event is not None
    await db_session.flush()

    with pytest.raises(Exception, match="immutable"):
        await db_session.execute(
            sa.text("DELETE FROM audit_event WHERE id = :id").bindparams(id=event.id)
        )
        await db_session.flush()
