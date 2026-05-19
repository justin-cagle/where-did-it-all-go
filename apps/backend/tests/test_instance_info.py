"""Integration tests for GET /api/v1/settings/instance-info.

pytest -m integration tests/test_instance_info.py
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    aio_mode: bool = False,
    postgres_url: str,
) -> None:
    import app.settings.router as router_module
    from app import config as cfg_module
    from app.config import Settings

    if hasattr(cfg_module.get_settings, "cache_clear"):
        cfg_module.get_settings.cache_clear()

    settings = Settings(  # type: ignore[arg-type]
        database_url=postgres_url,
        master_key="test-key-not-for-production",
        bootstrap_admin_email="admin@test.com",
        bootstrap_admin_password="adminpass123",  # pragma: allowlist secret
        aio_mode=aio_mode,
        app_version="0.3.1",
    )
    monkeypatch.setattr(cfg_module, "get_settings", lambda: settings)
    monkeypatch.setattr(router_module, "get_settings", lambda: settings)


_TRUNCATE = sa.text(
    "DO $$ DECLARE r RECORD; BEGIN "
    "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
    "EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; "
    "END LOOP; END $$;"
)


@pytest.fixture()
async def client(  # type: ignore[misc]
    postgres_url: str, db_engine, session_factory, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    import app.database as db_module
    from app.main import create_app

    _patch_settings(monkeypatch, aio_mode=False, postgres_url=postgres_url)
    db_module._engine = db_engine  # type: ignore[assignment]
    db_module._session_factory = session_factory  # type: ignore[assignment]

    application = create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        yield ac

    async with db_engine.connect() as conn:
        await conn.execute(_TRUNCATE)
        await conn.commit()


@pytest.fixture()
async def aio_client(  # type: ignore[misc]
    postgres_url: str, db_engine, session_factory, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    import app.database as db_module
    from app.main import create_app

    _patch_settings(monkeypatch, aio_mode=True, postgres_url=postgres_url)
    db_module._engine = db_engine  # type: ignore[assignment]
    db_module._session_factory = session_factory  # type: ignore[assignment]

    application = create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        yield ac

    async with db_engine.connect() as conn:
        await conn.execute(_TRUNCATE)
        await conn.commit()


async def test_instance_info_default(client: AsyncClient) -> None:
    """AIO_MODE=false returns aio_mode=false, demo_credentials=null."""
    resp = await client.get("/api/v1/settings/instance-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["aio_mode"] is False
    assert body["demo_credentials"] is None
    assert body["version"] == "0.3.1"


async def test_instance_info_no_auth_required(client: AsyncClient) -> None:
    """Unauthenticated request returns 200."""
    resp = await client.get("/api/v1/settings/instance-info")
    assert resp.status_code == 200


async def test_instance_info_aio_mode(aio_client: AsyncClient) -> None:
    """AIO_MODE=true returns aio_mode=true and demo_credentials."""
    resp = await aio_client.get("/api/v1/settings/instance-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["aio_mode"] is True
    creds = body["demo_credentials"]
    assert creds is not None
    assert creds["email"] == "admin@wdiag.local"
    assert creds["password"] == "admin"  # pragma: allowlist secret
