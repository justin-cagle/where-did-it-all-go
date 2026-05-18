"""Integration tests for cleanup_unassigned_accounts ARQ job.

pytest -m integration
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.households import service
from app.households.jobs import cleanup_unassigned_accounts
from app.households.models import User

pytestmark = pytest.mark.integration

_JWT = "test-jwt-secret"


@pytest.fixture()
async def session(postgres_url: str) -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app import database as db_module

    factory = async_sessionmaker(engine, expire_on_commit=False)
    db_module._engine = engine
    db_module._session_factory = factory

    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _patch_settings(monkeypatch: pytest.MonkeyPatch, ttl_days: int = 7) -> None:
    import app.households.jobs as jobs_module
    from app import config as cfg_module
    from app.config import Settings

    cfg_module.get_settings.cache_clear()
    settings = Settings(  # type: ignore[arg-type]
        database_url="postgresql+asyncpg://fake/fake",
        master_key="test-key",
        bootstrap_admin_email="admin@test.com",
        bootstrap_admin_password="adminpass123",  # pragma: allowlist secret
        unassigned_account_ttl_days=ttl_days,
    )
    monkeypatch.setattr(cfg_module, "get_settings", lambda: settings)
    monkeypatch.setattr(jobs_module, "get_settings", lambda: settings)


async def _create_old_user(session: AsyncSession, email: str, days_ago: int) -> User:
    user = await service.create_user(
        session,
        email=email,
        display_name="Test",
        password="password123",  # pragma: allowlist secret
    )
    await session.flush()
    cutoff = datetime.now(tz=UTC) - timedelta(days=days_ago)
    await session.execute(sa.update(User).where(User.id == user.id).values(created_at=cutoff))
    await session.commit()
    return user


async def test_cleanup_deletes_past_ttl(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User with no membership, past TTL → hard deleted."""
    _patch_settings(monkeypatch, ttl_days=7)

    user = await _create_old_user(session, "victim@example.com", days_ago=8)
    user_id = user.id

    result = await cleanup_unassigned_accounts({})
    assert result["deleted"] == 1

    # User should be gone
    found = await session.execute(
        sa.select(User).where(User.id == user_id).execution_options(include_archived=True)
    )
    assert found.scalar_one_or_none() is None


async def test_cleanup_exempts_recent_accounts(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User with no membership but within TTL → not deleted."""
    _patch_settings(monkeypatch, ttl_days=7)

    user = await _create_old_user(session, "recent@example.com", days_ago=3)
    user_id = user.id

    result = await cleanup_unassigned_accounts({})
    assert result["deleted"] == 0

    found = await session.execute(
        sa.select(User).where(User.id == user_id).execution_options(include_archived=True)
    )
    assert found.scalar_one_or_none() is not None


async def test_cleanup_exempts_members(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User with household membership → exempt even if past TTL."""
    from app.households.enums import VisibilityMode

    _patch_settings(monkeypatch, ttl_days=7)

    user = await _create_old_user(session, "member@example.com", days_ago=10)

    await service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    await session.commit()

    result = await cleanup_unassigned_accounts({})
    assert result["deleted"] == 0


async def test_cleanup_skipped_when_ttl_zero(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TTL=0 → cleanup job skips entirely."""
    _patch_settings(monkeypatch, ttl_days=0)

    await _create_old_user(session, "skip@example.com", days_ago=999)

    result = await cleanup_unassigned_accounts({})
    assert result.get("skipped_ttl_disabled") is True
    assert result["deleted"] == 0
