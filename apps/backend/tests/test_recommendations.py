"""Tests for the recommendations module.

Unit tests (no DB) run without any external services.
Integration tests (marked @pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests cover:
  - Status transitions: pending->accepted/rejected are legal; accepted/rejected/expired
    are terminal — no further transitions allowed
  - Expiry: expires_at in past -> status=expired on expire_stale sweep;
    no expiry when expires_at is null
  - Auto-apply is advisory: should_auto_apply() returns the flag but does NOT
    change Recommendation.status; caller must still call accept() explicitly
  - AuditLog on accept carries rationale_text forward
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.accounts.models
import app.audit.models
import app.classification.models
import app.households.models
import app.recommendations.models
import app.transactions.models  # noqa: F401
from app.audit.models import AuditEvent
from app.database import Base
from app.households.enums import VisibilityMode
from app.households.service import create_household, create_user
from app.recommendations.enums import RecommendationSource, RecommendationStatus
from app.recommendations.models import AutoApplyRule, Recommendation
from app.recommendations.service import (
    ConflictError,
    NotFoundError,
    accept,
    create,
    expire_stale,
    get,
    get_auto_apply_rule,
    list_pending,
    reject,
    set_auto_apply,
    should_auto_apply,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_source = st.sampled_from(list(RecommendationSource))
_status = st.sampled_from(list(RecommendationStatus))
_terminal_status = st.sampled_from(
    [RecommendationStatus.ACCEPTED, RecommendationStatus.REJECTED, RecommendationStatus.EXPIRED]
)


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestRecommendationSourceEnum:
    def test_all_sources_are_strings(self) -> None:
        for s in RecommendationSource:
            assert isinstance(str(s), str)
            assert str(s) == s.value

    def test_ingest_value(self) -> None:
        assert str(RecommendationSource.INGEST) == "ingest"

    def test_classification_pipeline_value(self) -> None:
        assert str(RecommendationSource.CLASSIFICATION_PIPELINE) == "classification_pipeline"


class TestRecommendationStatusEnum:
    def test_pending_is_non_terminal(self) -> None:
        non_terminal = {RecommendationStatus.PENDING}
        terminal = {
            RecommendationStatus.ACCEPTED,
            RecommendationStatus.REJECTED,
            RecommendationStatus.EXPIRED,
        }
        assert non_terminal | terminal == set(RecommendationStatus)


# ===========================================================================
# Hypothesis property tests — pure (no DB)
# ===========================================================================


@given(_source)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_source_str_roundtrip(source: RecommendationSource) -> None:
    """str(source) == source.value and RecommendationSource(str(source)) == source."""
    assert RecommendationSource(str(source)) == source


@given(_status)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_status_str_roundtrip(status: RecommendationStatus) -> None:
    """str(status) == status.value and RecommendationStatus(str(status)) == status."""
    assert RecommendationStatus(str(status)) == status


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
    """Seed a household + user."""
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
    await db.commit()
    return {"user": user, "household": household}


async def _make_rec(
    db: AsyncSession,
    household_id: uuid.UUID,
    *,
    source: RecommendationSource = RecommendationSource.INGEST,
    target_subsystem: str = "transactions",
    rationale_text: str = "test rationale",
    expires_at: datetime | None = None,
) -> Recommendation:
    rec = await create(
        db,
        household_id=household_id,
        source=source,
        target_subsystem=target_subsystem,
        rationale_text=rationale_text,
        expires_at=expires_at,
    )
    await db.flush()
    return rec


# ---------------------------------------------------------------------------
# create + get
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_recommendation(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    rec = await _make_rec(db, hh.id)
    await db.commit()

    fetched = await get(db, recommendation_id=rec.id, household_id=hh.id)
    assert fetched.id == rec.id
    assert fetched.status == str(RecommendationStatus.PENDING)
    assert fetched.source == str(RecommendationSource.INGEST)
    assert fetched.auto_apply is False
    assert fetched.resolved_at is None
    assert fetched.resolved_by is None


@pytest.mark.integration
async def test_get_not_found(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    with pytest.raises(NotFoundError):
        await get(db, recommendation_id=uuid.uuid4(), household_id=hh.id)


@pytest.mark.integration
async def test_get_wrong_household(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    rec = await _make_rec(db, hh.id)
    await db.commit()

    with pytest.raises(NotFoundError):
        await get(db, recommendation_id=rec.id, household_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_accept_pending(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    rec = await _make_rec(db, hh.id, rationale_text="Possible duplicate found.")
    await db.commit()

    accepted = await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    assert accepted.status == str(RecommendationStatus.ACCEPTED)
    assert accepted.resolved_by == user.id
    assert accepted.resolved_at is not None


@pytest.mark.integration
async def test_reject_pending(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    user = seed["user"]
    rec = await _make_rec(db, hh.id)
    await db.commit()

    rejected = await reject(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    assert rejected.status == str(RecommendationStatus.REJECTED)
    assert rejected.resolved_by == user.id
    assert rejected.resolved_at is not None


@pytest.mark.integration
async def test_accept_is_terminal(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Accepted recommendation cannot be accepted or rejected again."""
    hh = seed["household"]
    user = seed["user"]
    rec = await _make_rec(db, hh.id)
    await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    with pytest.raises(ConflictError, match="accepted"):
        await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)

    with pytest.raises(ConflictError, match="accepted"):
        await reject(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)


@pytest.mark.integration
async def test_rejected_is_terminal(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Rejected recommendation cannot be accepted or rejected again."""
    hh = seed["household"]
    user = seed["user"]
    rec = await _make_rec(db, hh.id)
    await reject(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    with pytest.raises(ConflictError, match="rejected"):
        await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)

    with pytest.raises(ConflictError, match="rejected"):
        await reject(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)


@pytest.mark.integration
async def test_expired_is_terminal(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Expired recommendation cannot be accepted or rejected."""
    hh = seed["household"]
    user = seed["user"]
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    rec = await _make_rec(db, hh.id, expires_at=past)
    await expire_stale(db)
    await db.commit()

    with pytest.raises(ConflictError, match="expired"):
        await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_expire_stale_past_expires_at(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Recommendation with expires_at in the past is expired by the sweep."""
    hh = seed["household"]
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    rec = await _make_rec(db, hh.id, expires_at=past)
    await db.commit()

    expired = await expire_stale(db)
    await db.commit()

    assert len(expired) == 1
    assert expired[0].id == rec.id
    assert expired[0].status == str(RecommendationStatus.EXPIRED)


@pytest.mark.integration
async def test_expire_stale_future_expires_at_not_expired(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    """Recommendation with future expires_at is NOT expired by the sweep."""
    hh = seed["household"]
    future = datetime.now(tz=UTC) + timedelta(days=1)
    await _make_rec(db, hh.id, expires_at=future)
    await db.commit()

    expired = await expire_stale(db)
    await db.commit()

    assert expired == []


@pytest.mark.integration
async def test_expire_stale_null_expires_at_never_expires(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    """Recommendation with no expires_at is never expired by the sweep."""
    hh = seed["household"]
    await _make_rec(db, hh.id, expires_at=None)
    await db.commit()

    expired = await expire_stale(db)
    await db.commit()

    assert expired == []


@pytest.mark.integration
async def test_expire_stale_idempotent(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Running expire_stale twice on the same row only expires once."""
    hh = seed["household"]
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    await _make_rec(db, hh.id, expires_at=past)
    await db.commit()

    first = await expire_stale(db)
    await db.commit()
    second = await expire_stale(db)
    await db.commit()

    assert len(first) == 1
    assert len(second) == 0


# ---------------------------------------------------------------------------
# Audit log on accept
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_accept_writes_audit_with_rationale(db: AsyncSession, seed: dict[str, Any]) -> None:
    """accept() writes an AuditEvent with rationale_text carried forward."""
    hh = seed["household"]
    user = seed["user"]
    rationale = "Fuzzy match confidence 0.91 — possible duplicate transaction."
    rec = await _make_rec(db, hh.id, rationale_text=rationale)
    await db.commit()

    await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    result = await db.execute(
        sa.select(AuditEvent).where(
            AuditEvent.entity_type == "recommendation",
            AuditEvent.entity_id == rec.id,
            AuditEvent.operation == "accept",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.rationale == rationale
    assert audit.actor_id == user.id
    assert audit.actor_source == "recommendation_hitl"


@pytest.mark.integration
async def test_reject_writes_audit(db: AsyncSession, seed: dict[str, Any]) -> None:
    """reject() writes an AuditEvent."""
    hh = seed["household"]
    user = seed["user"]
    rec = await _make_rec(db, hh.id)
    await db.commit()

    await reject(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    result = await db.execute(
        sa.select(AuditEvent).where(
            AuditEvent.entity_type == "recommendation",
            AuditEvent.entity_id == rec.id,
            AuditEvent.operation == "reject",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.actor_id == user.id


# ---------------------------------------------------------------------------
# list_pending
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_pending_returns_pending_by_default(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    user = seed["user"]

    r1 = await _make_rec(db, hh.id)
    r2 = await _make_rec(db, hh.id)
    r3 = await _make_rec(db, hh.id)
    await accept(db, recommendation_id=r3.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    pending = await list_pending(db, household_id=hh.id)
    ids = {r.id for r in pending}
    assert r1.id in ids
    assert r2.id in ids
    assert r3.id not in ids


@pytest.mark.integration
async def test_list_pending_filter_by_source(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    await _make_rec(db, hh.id, source=RecommendationSource.INGEST)
    await _make_rec(db, hh.id, source=RecommendationSource.CLASSIFICATION_PIPELINE)
    await db.commit()

    ingest_only = await list_pending(db, household_id=hh.id, source=RecommendationSource.INGEST)
    assert all(r.source == str(RecommendationSource.INGEST) for r in ingest_only)
    assert len(ingest_only) == 1


@pytest.mark.integration
async def test_list_pending_filter_by_target_subsystem(
    db: AsyncSession, seed: dict[str, Any]
) -> None:
    hh = seed["household"]
    await _make_rec(db, hh.id, target_subsystem="transactions")
    await _make_rec(db, hh.id, target_subsystem="budgets")
    await db.commit()

    tx_only = await list_pending(db, household_id=hh.id, target_subsystem="transactions")
    assert all(r.target_subsystem == "transactions" for r in tx_only)
    assert len(tx_only) == 1


# ---------------------------------------------------------------------------
# Auto-apply: advisory, never mutates Recommendation.status
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_auto_apply_default_false(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Auto-apply defaults to False for any source."""
    hh = seed["household"]
    enabled = await get_auto_apply_rule(db, household_id=hh.id, source=RecommendationSource.INGEST)
    assert enabled is False


@pytest.mark.integration
async def test_set_auto_apply_persists(db: AsyncSession, seed: dict[str, Any]) -> None:
    hh = seed["household"]
    await set_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST, enabled=True)
    await db.commit()

    enabled = await get_auto_apply_rule(db, household_id=hh.id, source=RecommendationSource.INGEST)
    assert enabled is True


@pytest.mark.integration
async def test_set_auto_apply_upsert(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Calling set_auto_apply twice does not create duplicate rows."""
    hh = seed["household"]
    await set_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST, enabled=True)
    await set_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST, enabled=False)
    await db.commit()

    result = await db.execute(
        sa.select(AutoApplyRule).where(
            AutoApplyRule.household_id == hh.id,
            AutoApplyRule.source == str(RecommendationSource.INGEST),
        )
    )
    rules = list(result.scalars().all())
    assert len(rules) == 1
    assert rules[0].enabled is False


@pytest.mark.integration
async def test_should_auto_apply_advisory_only(db: AsyncSession, seed: dict[str, Any]) -> None:
    """should_auto_apply() returns True but does NOT change Recommendation.status.

    The auto-apply flag is advisory. Caller must still call accept() explicitly.
    """
    hh = seed["household"]
    await set_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST, enabled=True)
    rec = await _make_rec(db, hh.id, source=RecommendationSource.INGEST)
    await db.commit()

    flag = await should_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST)
    assert flag is True

    # Status must still be pending — should_auto_apply does nothing to the recommendation
    fetched = await get(db, recommendation_id=rec.id, household_id=hh.id)
    assert fetched.status == str(RecommendationStatus.PENDING)


@pytest.mark.integration
async def test_auto_apply_per_source_isolated(db: AsyncSession, seed: dict[str, Any]) -> None:
    """Enabling auto-apply for one source does not affect other sources."""
    hh = seed["household"]
    await set_auto_apply(db, household_id=hh.id, source=RecommendationSource.INGEST, enabled=True)
    await db.commit()

    classification_flag = await should_auto_apply(
        db,
        household_id=hh.id,
        source=RecommendationSource.CLASSIFICATION_PIPELINE,
    )
    assert classification_flag is False


# ---------------------------------------------------------------------------
# Hypothesis property tests — DB-backed status machine
# ---------------------------------------------------------------------------


@given(
    st.booleans(),  # accept (True) or reject (False)
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=10)
def test_pending_to_resolved_is_terminal_property(accept_not_reject: bool) -> None:
    """Pending->resolved always succeeds; resolved->any raises ConflictError.

    Verified via logic inspection — the _assert_pending guard must fire on
    any non-pending status.
    """
    from app.recommendations.models import Recommendation
    from app.recommendations.service import _assert_pending  # type: ignore[attr-defined]

    for terminal in [
        str(RecommendationStatus.ACCEPTED),
        str(RecommendationStatus.REJECTED),
        str(RecommendationStatus.EXPIRED),
    ]:
        rec = Recommendation(status=terminal)
        op = "accept" if accept_not_reject else "reject"
        try:
            _assert_pending(rec, op)
            raise AssertionError("should have raised ConflictError")
        except ConflictError:
            pass  # expected

    # Pending always passes
    rec = Recommendation(status=str(RecommendationStatus.PENDING))
    _assert_pending(rec, "accept")  # must not raise


# ===========================================================================
# Schema tests
# ===========================================================================


class TestSchemas:
    def test_recommendation_out_from_attributes(self) -> None:
        from app.recommendations.schemas import RecommendationOut

        now = datetime.now(tz=UTC)
        rec = Recommendation(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            source=str(RecommendationSource.INGEST),
            target_subsystem="transactions",
            target_entity_id=None,
            proposed_value={"key": "val"},
            rationale_text="test",
            rationale_data={},
            confidence=None,
            status=str(RecommendationStatus.PENDING),
            expires_at=None,
            resolved_at=None,
            resolved_by=None,
            auto_apply=False,
            created_at=now,
            updated_at=now,
        )
        out = RecommendationOut.model_validate(rec)
        assert out.status == RecommendationStatus.PENDING
        assert out.source == RecommendationSource.INGEST
        assert out.auto_apply is False

    def test_auto_apply_rule_out(self) -> None:
        from app.recommendations.schemas import AutoApplyRuleOut

        now = datetime.now(tz=UTC)
        rule = AutoApplyRule(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            source=str(RecommendationSource.CLASSIFICATION_PIPELINE),
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        out = AutoApplyRuleOut.model_validate(rule)
        assert out.source == RecommendationSource.CLASSIFICATION_PIPELINE
        assert out.enabled is True

    def test_auto_apply_toggle_schema(self) -> None:
        from app.recommendations.schemas import AutoApplyToggle

        t = AutoApplyToggle(enabled=True)
        assert t.enabled is True
        t2 = AutoApplyToggle(enabled=False)
        assert t2.enabled is False


# ===========================================================================
# Model __repr__ tests
# ===========================================================================


class TestModelRepr:
    def test_recommendation_repr(self) -> None:
        rec = Recommendation(
            id=uuid.uuid4(),
            source=str(RecommendationSource.INGEST),
            status=str(RecommendationStatus.PENDING),
            target_subsystem="transactions",
        )
        r = repr(rec)
        assert "Recommendation" in r
        assert "ingest" in r
        assert "pending" in r

    def test_auto_apply_rule_repr(self) -> None:
        rule = AutoApplyRule(
            id=uuid.uuid4(),
            source=str(RecommendationSource.INGEST),
            enabled=True,
        )
        r = repr(rule)
        assert "AutoApplyRule" in r
        assert "ingest" in r


# ===========================================================================
# Job tests
# ===========================================================================


@pytest.mark.asyncio
async def test_expire_stale_recommendations_job() -> None:
    """Job calls expire_stale and commits via session factory."""
    from unittest.mock import MagicMock

    from app.recommendations.jobs import expire_stale_recommendations_job

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock()
    mock_factory.return_value = mock_ctx

    with patch("app.recommendations.jobs.get_session_factory", return_value=mock_factory):
        with patch(
            "app.recommendations.service.expire_stale", new_callable=AsyncMock
        ) as mock_expire:
            mock_expire.return_value = []
            result = await expire_stale_recommendations_job({})

    assert result == {"expired": 0}


# ===========================================================================
# Router integration tests (AsyncClient + dependency overrides)
# ===========================================================================


@pytest.fixture()
async def api_client(
    db: AsyncSession,
    seed: dict[str, Any],
) -> AsyncGenerator[tuple[AsyncClient, Any, Any], None]:
    """Yield an httpx AsyncClient wired to a minimal FastAPI app (recommendations router only).

    Does not use create_app() / get_settings() — avoids env-var requirements in test env.
    """
    from fastapi import FastAPI

    from app.database import get_db
    from app.households.deps import get_current_user
    from app.recommendations.deps import _require_household_member
    from app.recommendations.router import router

    hh = seed["household"]
    user = seed["user"]

    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1")

    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    async def _current_user() -> Any:
        return user

    async def _household_member(household_id: uuid.UUID) -> uuid.UUID:
        return household_id

    _app.dependency_overrides[get_db] = _get_db
    _app.dependency_overrides[get_current_user] = _current_user
    _app.dependency_overrides[_require_household_member] = _household_member

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        yield client, hh, user


@pytest.mark.integration
async def test_router_list_recommendations_empty(
    api_client: tuple[AsyncClient, Any, Any],
) -> None:
    client, hh, _ = api_client
    resp = await client.get(f"/api/v1/households/{hh.id}/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.integration
async def test_router_get_recommendation(
    api_client: tuple[AsyncClient, Any, Any],
    db: AsyncSession,
    seed: dict[str, Any],
) -> None:
    client, hh, _ = api_client
    rec = await _make_rec(db, hh.id)
    await db.commit()

    resp = await client.get(f"/api/v1/households/{hh.id}/recommendations/{rec.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(rec.id)
    assert data["status"] == "pending"


@pytest.mark.integration
async def test_router_get_recommendation_not_found(
    api_client: tuple[AsyncClient, Any, Any],
) -> None:
    client, hh, _ = api_client
    resp = await client.get(f"/api/v1/households/{hh.id}/recommendations/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.integration
async def test_router_accept_recommendation(
    api_client: tuple[AsyncClient, Any, Any],
    db: AsyncSession,
    seed: dict[str, Any],
) -> None:
    client, hh, _ = api_client
    rec = await _make_rec(db, hh.id)
    await db.commit()

    resp = await client.post(f"/api/v1/households/{hh.id}/recommendations/{rec.id}/accept")
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@pytest.mark.integration
async def test_router_accept_twice_returns_conflict(
    api_client: tuple[AsyncClient, Any, Any],
    db: AsyncSession,
    seed: dict[str, Any],
) -> None:
    client, hh, _ = api_client
    rec = await _make_rec(db, hh.id)
    await db.commit()

    await client.post(f"/api/v1/households/{hh.id}/recommendations/{rec.id}/accept")
    resp = await client.post(f"/api/v1/households/{hh.id}/recommendations/{rec.id}/accept")
    assert resp.status_code == 409


@pytest.mark.integration
async def test_router_reject_recommendation(
    api_client: tuple[AsyncClient, Any, Any],
    db: AsyncSession,
    seed: dict[str, Any],
) -> None:
    client, hh, _ = api_client
    rec = await _make_rec(db, hh.id)
    await db.commit()

    resp = await client.post(f"/api/v1/households/{hh.id}/recommendations/{rec.id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.integration
async def test_router_list_auto_apply_empty(
    api_client: tuple[AsyncClient, Any, Any],
) -> None:
    client, hh, _ = api_client
    resp = await client.get(f"/api/v1/households/{hh.id}/recommendations/auto-apply")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.integration
async def test_router_toggle_auto_apply(
    api_client: tuple[AsyncClient, Any, Any],
) -> None:
    client, hh, _ = api_client
    resp = await client.post(
        f"/api/v1/households/{hh.id}/recommendations/auto-apply/ingest",
        json={"enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "ingest"
    assert data["enabled"] is True


@pytest.mark.integration
async def test_router_list_recommendations_filter_by_status(
    api_client: tuple[AsyncClient, Any, Any],
    db: AsyncSession,
    seed: dict[str, Any],
) -> None:
    client, hh, user = api_client
    rec = await _make_rec(db, hh.id)
    await accept(db, recommendation_id=rec.id, household_id=hh.id, user_id=user.id)
    await db.commit()

    # Default filter: pending
    resp = await client.get(f"/api/v1/households/{hh.id}/recommendations")
    assert resp.status_code == 200
    pending = resp.json()
    assert all(r["status"] == "pending" for r in pending)

    # Filter by accepted
    resp = await client.get(
        f"/api/v1/households/{hh.id}/recommendations", params={"status": "accepted"}
    )
    assert resp.status_code == 200
    accepted_list = resp.json()
    assert any(r["id"] == str(rec.id) for r in accepted_list)
