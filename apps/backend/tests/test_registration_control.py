"""Integration tests for registration control (ALLOW_REGISTRATION, REGISTRATION_LIMIT).

pytest -m integration
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

from app.main import create_app

pytestmark = pytest.mark.integration

_REGISTER_URL = "/api/v1/auth/register"
_SETTINGS_URL = "/api/v1/settings/registration"
_PAYLOAD = {
    "email": "test@example.com",
    "display_name": "Test User",
    "password": "password123",  # pragma: allowlist secret
}


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
async def client(db_engine, session_factory, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:  # type: ignore[misc]
    """ASGI test client wired to a real test database."""
    from app import database as db_module

    db_module._engine = db_engine
    db_module._session_factory = session_factory

    _patch_settings(monkeypatch, allow_registration=True)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    async with db_engine.connect() as conn:
        await conn.execute(
            sa.text(
                "DO $$ DECLARE r RECORD; BEGIN "
                "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
                "EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; "
                "END LOOP; END $$;"
            )
        )
        await conn.commit()


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
