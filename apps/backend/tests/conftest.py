"""Pytest configuration and shared fixtures.

Fast (unit) tests run without any external services.
Integration tests (marked with @pytest.mark.integration) use testcontainers
to spin up real Postgres and Redis instances.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base

# ---------------------------------------------------------------------------
# Integration fixtures — only instantiated when -m integration is used
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


@pytest.fixture()
async def db_session(postgres_url: str) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session connected to the integration test database.

    Creates all tables before the test and drops them after.
    """
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
