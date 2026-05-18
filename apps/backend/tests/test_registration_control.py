"""Integration tests for registration control (ALLOW_REGISTRATION, REGISTRATION_LIMIT).

pytest -m integration
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.main import create_app

pytestmark = pytest.mark.integration

_REGISTER_URL = "/api/v1/auth/register"
_SETTINGS_URL = "/api/v1/settings/registration"
_PAYLOAD = {
    "email": "test@example.com",
    "display_name": "Test User",
    "password": "password123",  # pragma: allowlist secret
}


@pytest.fixture()
async def db_session(postgres_url: str) -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    from app import config as cfg_module
    from app.config import Settings

    if hasattr(cfg_module.get_settings, "cache_clear"):
        cfg_module.get_settings.cache_clear()
    base = {
        "database_url": "postgresql+asyncpg://fake/fake",
        "master_key": "test-key",
        "bootstrap_admin_email": "admin@example.com",
        "bootstrap_admin_password": "adminpass123",  # pragma: allowlist secret
    }
    base.update(overrides)
    settings = Settings(**base)  # type: ignore[arg-type]
    monkeypatch.setattr(cfg_module, "get_settings", lambda: settings)


@pytest.fixture()
async def client(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:  # type: ignore[misc]
    """ASGI test client wired to a real test database."""
    from app import database as db_module

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    db_module._engine = engine
    db_module._session_factory = factory

    _patch_settings(monkeypatch, allow_registration=True)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_registration_closed_returns_403(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ALLOW_REGISTRATION=False, no invite → 403 registration_closed."""
    _patch_settings(monkeypatch, allow_registration=False)
    resp = await client.post(_REGISTER_URL, json=_PAYLOAD)
    assert resp.status_code == 403
    body = resp.json()
    assert body["type"] == "registration_closed"


async def test_registration_open_succeeds(client: AsyncClient) -> None:
    """ALLOW_REGISTRATION=True, no limit → 201."""
    resp = await client.post(_REGISTER_URL, json=_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "user_id" in body
    assert body["redirect"] in ("/onboarding", "/waiting")


async def test_registration_limit_reached_returns_403(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ALLOW_REGISTRATION=True, limit=1, active=1, no invite → 403."""
    _patch_settings(monkeypatch, allow_registration=True, registration_limit=1)

    # Fill the limit
    r1 = await client.post(_REGISTER_URL, json=_PAYLOAD)
    assert r1.status_code == 201

    # Next attempt should be blocked
    resp = await client.post(
        _REGISTER_URL,
        json={**_PAYLOAD, "email": "other@example.com"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["type"] == "registration_limit_reached"


async def test_settings_endpoint_returns_config(client: AsyncClient) -> None:
    """GET /api/v1/settings/registration returns correct shape."""
    resp = await client.get(_SETTINGS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert "allow_registration" in body
    assert "registration_limit" in body
    assert "unassigned_account_ttl_days" in body
