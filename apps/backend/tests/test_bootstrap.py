"""Integration tests for the bootstrap service.

pytest -m integration
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base
from app.households import service
from app.households.bootstrap import run_bootstrap

pytestmark = pytest.mark.integration


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


@pytest.fixture()
def bootstrap_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch get_settings to return a Settings with bootstrap vars set."""
    from app import config as cfg_module

    original = cfg_module.get_settings
    original.cache_clear()

    settings = Settings(  # type: ignore[call-arg]
        database_url="postgresql+asyncpg://fake/fake",
        master_key="test-master-key",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="supersecret123",  # pragma: allowlist secret
    )

    monkeypatch.setattr(cfg_module, "get_settings", lambda: settings)
    yield
    original.cache_clear()


@pytest.fixture()
def no_bootstrap_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch get_settings with no bootstrap vars set."""
    from app import config as cfg_module

    original = cfg_module.get_settings
    original.cache_clear()

    settings = Settings(  # type: ignore[call-arg]
        database_url="postgresql+asyncpg://fake/fake",
        master_key="test-master-key",
    )

    monkeypatch.setattr(cfg_module, "get_settings", lambda: settings)
    yield
    original.cache_clear()


async def test_bootstrap_creates_admin(session: AsyncSession, bootstrap_settings: None) -> None:
    """Empty DB + vars set → admin created with is_app_admin=True."""
    await run_bootstrap(session)

    user = await service.get_user_by_id(session, (await _get_first_user_id(session)))
    assert user is not None
    assert user.email == "admin@example.com"
    assert user.is_app_admin is True


async def test_bootstrap_skips_when_users_exist(
    session: AsyncSession, bootstrap_settings: None
) -> None:
    """Non-empty DB + vars set → no-op, no duplicate created."""
    import sqlalchemy as sa

    from app.households.models import User

    # Create an existing user first
    await service.create_user(
        session,
        email="existing@example.com",
        display_name="Existing",
        password="password123",  # pragma: allowlist secret
    )
    await session.commit()

    # Count before bootstrap
    count_before = (
        await session.execute(sa.select(sa.func.count()).select_from(User))
    ).scalar_one()

    await run_bootstrap(session)

    count_after = (await session.execute(sa.select(sa.func.count()).select_from(User))).scalar_one()
    assert count_after == count_before


async def test_bootstrap_refuses_when_no_vars(
    session: AsyncSession, no_bootstrap_settings: None
) -> None:
    """Empty DB + no vars → SystemExit raised."""
    with pytest.raises(SystemExit):
        await run_bootstrap(session)


async def _get_first_user_id(session: AsyncSession) -> object:
    import sqlalchemy as sa

    from app.households.models import User

    result = await session.execute(sa.select(User.id).limit(1))
    return result.scalar_one()
