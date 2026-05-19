"""Pytest configuration and shared fixtures.

Fast (unit) tests run without any external services.
Integration tests (marked with @pytest.mark.integration) use testcontainers
to spin up real Postgres and Redis instances.

Session-scoped Postgres and Redis containers start once per test run.
Per-test isolation is achieved via connection-level transaction rollback.
Tests that need real commits (ASGI clients, job tests) use TRUNCATE cleanup.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_TRUNCATE_ALL = sa.text(
    "DO $$ DECLARE r RECORD; BEGIN "
    "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
    "EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; "
    "END LOOP; END $$;"
)


def pytest_configure(config: pytest.Config) -> None:
    """Set minimal env vars so get_settings() works at import/collection time."""
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret
    )
    os.environ.setdefault("MASTER_KEY", "test-master-key-for-tests-only")


# ---------------------------------------------------------------------------
# Containers — session-scoped (one per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Spin up a Postgres container and return its connection URL.

    Requires Docker. Used only for integration tests.
    """
    pytest.importorskip("testcontainers")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as postgres:
        # testcontainers 4.x returns postgresql+psycopg2://; force asyncpg driver
        yield "postgresql+asyncpg://" + postgres.get_connection_url().split("://", 1)[1]


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Spin up a Redis container and return its connection URL."""
    pytest.importorskip("testcontainers")
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


# ---------------------------------------------------------------------------
# Session-scoped DB engine — all models imported, schema created once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def db_engine(postgres_url: str):
    """Create engine and schema once for the entire test session.

    All models are imported here so Base.metadata knows every table.
    Tests use transaction rollback for isolation; schema is never recreated.
    """
    import app.accounts.models
    import app.admin.models
    import app.audit.models
    import app.budgets.models
    import app.classification.models
    import app.debts.models
    import app.goals.models
    import app.households.models
    import app.ingest.models
    import app.insights.models
    import app.platform.fx
    import app.projections.models
    import app.recommendations.models
    import app.recurrences.models
    import app.transactions.models  # noqa: F401
    from app.database import Base

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine):
    """Session-scoped factory — reuse across tests."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Per-test isolation via connection-level transaction rollback
# ---------------------------------------------------------------------------


@pytest.fixture()
async def session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test DB session with automatic rollback.

    Uses join_transaction_mode='create_savepoint' so that test code calling
    session.commit() releases a savepoint rather than committing to the DB.
    The outer connection-level transaction is rolled back after each test.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        async_session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield async_session
        finally:
            await async_session.close()
            await conn.rollback()


@pytest.fixture()
async def db_session(session: AsyncSession) -> AsyncSession:
    """Alias for `session` — kept for backward compatibility."""
    return session


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_client(redis_url: str):
    """Session-scoped sync Redis client."""
    import redis as redis_lib

    client = redis_lib.Redis.from_url(redis_url)
    yield client
    client.close()


@pytest.fixture()
def flush_redis(redis_client) -> None:
    """Flush Redis after each test. Request this fixture in tests that touch Redis state."""
    yield
    redis_client.flushdb()
