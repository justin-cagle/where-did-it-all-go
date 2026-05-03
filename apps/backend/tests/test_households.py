"""Integration tests for the households module.

Requires a real Postgres instance (via testcontainers). Run with:
    pytest -m integration

Coverage targets:
  - create_user / authenticate_local
  - create_household / add_member / remove_member
  - issue_tokens / refresh_tokens (idle timeout sliding window)
  - revoke_all_tokens (logout)
  - step_up_auth

Hypothesis property tests:
  - Membership uniqueness invariant
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.households import service
from app.households.enums import HouseholdRole, VisibilityMode
from app.households.models import RefreshToken

_JWT_SECRET = "test-jwt-secret-not-for-production"  # pragma: allowlist secret

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def postgres_url_for_households(postgres_url: str) -> str:
    return postgres_url


@pytest.fixture()
async def session(postgres_url_for_households: str) -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(postgres_url_for_households)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# User + auth tests
# ---------------------------------------------------------------------------


async def test_create_user(session: AsyncSession) -> None:
    user = await service.create_user(
        session,
        email="alice@example.com",
        display_name="Alice",
        password="hunter2hunter2",
    )
    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.password_hash is not None
    assert not user.password_hash.startswith("hunter")  # hashed, not plaintext


async def test_create_user_duplicate_email_raises(session: AsyncSession) -> None:
    await service.create_user(
        session, email="bob@example.com", display_name="Bob", password="pw12345678"
    )
    with pytest.raises(service.ConflictError):
        await service.create_user(
            session, email="bob@example.com", display_name="Bob2", password="pw12345678"
        )


async def test_authenticate_local_success(session: AsyncSession) -> None:
    await service.create_user(
        session, email="carol@example.com", display_name="Carol", password="mypassword"
    )
    user = await service.authenticate_local(
        session, email="carol@example.com", password="mypassword", totp_code=None
    )
    assert user.email == "carol@example.com"


async def test_authenticate_local_wrong_password_raises(session: AsyncSession) -> None:
    await service.create_user(
        session, email="dave@example.com", display_name="Dave", password="correct"
    )
    with pytest.raises(service.AuthenticationError):
        await service.authenticate_local(
            session, email="dave@example.com", password="wrong", totp_code=None
        )


async def test_authenticate_local_unknown_email_raises(session: AsyncSession) -> None:
    with pytest.raises(service.AuthenticationError):
        await service.authenticate_local(
            session,
            email="nobody@example.com",
            password="anything",
            totp_code=None,
        )


# ---------------------------------------------------------------------------
# Token issuance and refresh tests
# ---------------------------------------------------------------------------


async def test_issue_tokens_returns_two_strings(session: AsyncSession) -> None:
    user = await service.create_user(
        session, email="eve@example.com", display_name="Eve", password="evepw1234"
    )
    access, refresh = await service.issue_tokens(
        session, user=user, household_id=None, jwt_secret=_JWT_SECRET
    )
    assert isinstance(access, str) and "." in access
    assert isinstance(refresh, str) and len(refresh) > 20


async def test_refresh_tokens_rotates_successfully(session: AsyncSession) -> None:
    user = await service.create_user(
        session, email="frank@example.com", display_name="Frank", password="frankpw!"
    )
    _, raw_refresh = await service.issue_tokens(
        session, user=user, household_id=None, jwt_secret=_JWT_SECRET
    )
    new_access, new_refresh = await service.refresh_tokens(
        session, raw_refresh_token=raw_refresh, jwt_secret=_JWT_SECRET
    )
    assert isinstance(new_access, str)
    assert new_refresh != raw_refresh  # token was rotated


async def test_refresh_tokens_old_token_is_revoked(session: AsyncSession) -> None:
    user = await service.create_user(
        session, email="grace@example.com", display_name="Grace", password="gracepw1"
    )
    _, raw_refresh = await service.issue_tokens(
        session, user=user, household_id=None, jwt_secret=_JWT_SECRET
    )
    await service.refresh_tokens(session, raw_refresh_token=raw_refresh, jwt_secret=_JWT_SECRET)
    # Old token must now be rejected
    with pytest.raises(service.AuthenticationError):
        await service.refresh_tokens(session, raw_refresh_token=raw_refresh, jwt_secret=_JWT_SECRET)


async def test_refresh_tokens_invalid_token_raises(session: AsyncSession) -> None:
    user = await service.create_user(
        session, email="henry@example.com", display_name="Henry", password="henrypw1"
    )
    await service.issue_tokens(session, user=user, household_id=None, jwt_secret=_JWT_SECRET)
    with pytest.raises(service.AuthenticationError):
        await service.refresh_tokens(
            session, raw_refresh_token="bogus-token", jwt_secret=_JWT_SECRET
        )


async def test_revoke_all_tokens_prevents_refresh(session: AsyncSession) -> None:
    user = await service.create_user(
        session, email="iris@example.com", display_name="Iris", password="irispwd1"
    )
    _, raw_refresh = await service.issue_tokens(
        session, user=user, household_id=None, jwt_secret=_JWT_SECRET
    )
    await service.revoke_all_tokens(session, user_id=user.id)
    with pytest.raises(service.AuthenticationError):
        await service.refresh_tokens(session, raw_refresh_token=raw_refresh, jwt_secret=_JWT_SECRET)


async def test_idle_timeout_sliding_window(session: AsyncSession) -> None:
    """Token used within idle window succeeds; token unused past window is rejected."""
    import time_machine

    user = await service.create_user(
        session, email="jake@example.com", display_name="Jake", password="jakepwd1"
    )
    _, raw_refresh = await service.issue_tokens(
        session,
        user=user,
        household_id=None,
        jwt_secret=_JWT_SECRET,
        idle_timeout_seconds=60,  # 1-minute idle window for test speed
    )

    # Use within the window → should succeed
    t_use = datetime.now(tz=UTC) + timedelta(seconds=30)
    with time_machine.travel(t_use):
        _, rotated = await service.refresh_tokens(
            session, raw_refresh_token=raw_refresh, jwt_secret=_JWT_SECRET
        )

    # Use the rotated token 90 seconds after last use → idle timeout
    t_expired = t_use + timedelta(seconds=90)
    with time_machine.travel(t_expired):
        with pytest.raises(service.AuthenticationError, match="idle timeout"):
            await service.refresh_tokens(session, raw_refresh_token=rotated, jwt_secret=_JWT_SECRET)


# ---------------------------------------------------------------------------
# Household CRUD tests
# ---------------------------------------------------------------------------


async def test_create_household(session: AsyncSession) -> None:
    owner = await service.create_user(
        session, email="owner@example.com", display_name="Owner", password="ownerpw1"
    )
    hh = await service.create_household(
        session,
        name="Smith Family",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=owner,
    )
    assert hh.id is not None
    assert hh.name == "Smith Family"
    assert hh.home_currency == "USD"


async def test_get_household_requires_membership(session: AsyncSession) -> None:
    owner = await service.create_user(
        session, email="owner2@example.com", display_name="O2", password="owner2pw1"
    )
    outsider = await service.create_user(
        session, email="outsider@example.com", display_name="Out", password="outsider1"
    )
    hh = await service.create_household(
        session,
        name="Private",
        visibility_mode=VisibilityMode.ADMIN_CONTROLLED,
        home_currency="GBP",
        owner=owner,
    )
    with pytest.raises(service.NotFoundError):
        await service.get_household(session, household_id=hh.id, actor=outsider)


async def test_list_households_returns_only_own(session: AsyncSession) -> None:
    u1 = await service.create_user(
        session, email="u1@example.com", display_name="U1", password="u1password"
    )
    u2 = await service.create_user(
        session, email="u2@example.com", display_name="U2", password="u2password"
    )
    await service.create_household(
        session,
        name="HH for U1",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=u1,
    )
    await service.create_household(
        session,
        name="HH for U2",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=u2,
    )
    households = await service.list_households(session, actor=u1)
    assert len(households) == 1
    assert households[0].name == "HH for U1"


# ---------------------------------------------------------------------------
# Membership invariant tests
# ---------------------------------------------------------------------------


async def test_add_member_requires_app_admin(session: AsyncSession) -> None:
    owner = await service.create_user(
        session,
        email="non_admin@example.com",
        display_name="NonAdmin",
        password="nonadmin1",
        is_app_admin=False,
    )
    hh = await service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=owner,
    )
    target = await service.create_user(
        session,
        email="target@example.com",
        display_name="Target",
        password="targetpw1",
    )
    with pytest.raises(service.PermissionError):
        await service.add_member(
            session,
            household_id=hh.id,
            email=target.email,
            role=HouseholdRole.MEMBER,
            actor=owner,  # owner but NOT app_admin
        )


async def test_add_and_remove_member(session: AsyncSession) -> None:
    admin = await service.create_user(
        session,
        email="admin_a@example.com",
        display_name="Admin",
        password="adminpw12",
        is_app_admin=True,
    )
    hh = await service.create_household(
        session,
        name="Admin HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=admin,
    )
    new_member = await service.create_user(
        session,
        email="new_member@example.com",
        display_name="New",
        password="newmember1",
    )

    membership = await service.add_member(
        session,
        household_id=hh.id,
        email=new_member.email,
        role=HouseholdRole.MEMBER,
        actor=admin,
    )
    assert membership.user_id == new_member.id

    # Duplicate add must be rejected
    with pytest.raises(service.ConflictError):
        await service.add_member(
            session,
            household_id=hh.id,
            email=new_member.email,
            role=HouseholdRole.MEMBER,
            actor=admin,
        )

    # Remove the member
    await service.remove_member(session, household_id=hh.id, user_id=new_member.id, actor=admin)
    members = await service.list_members(session, household_id=hh.id, actor=admin)
    member_ids = [m.user_id for m in members]
    assert new_member.id not in member_ids


# ---------------------------------------------------------------------------
# Hypothesis: membership uniqueness invariant
# ---------------------------------------------------------------------------


@given(roles=st.lists(st.sampled_from(list(HouseholdRole)), min_size=2, max_size=5))
@settings(max_examples=20)
def test_duplicate_membership_always_raises(roles: list[HouseholdRole]) -> None:
    """Adding the same user twice always raises ConflictError, regardless of role."""
    import asyncio

    async def _run() -> None:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

        with PostgresContainer("postgres:16") as pg:
            url = pg.get_connection_url().replace("postgresql://", "postgresql+asyncpg://")
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as s:
                admin = await service.create_user(
                    s,
                    email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
                    display_name="A",
                    password="adminpw12",
                    is_app_admin=True,
                )
                hh = await service.create_household(
                    s,
                    name="HH",
                    visibility_mode=VisibilityMode.FULLY_SHARED,
                    home_currency="USD",
                    owner=admin,
                )
                target = await service.create_user(
                    s,
                    email=f"t_{uuid.uuid4().hex[:8]}@test.com",
                    display_name="T",
                    password="targetpw1",
                )
                await service.add_member(
                    s,
                    household_id=hh.id,
                    email=target.email,
                    role=roles[0],
                    actor=admin,
                )
                with pytest.raises(service.ConflictError):
                    await service.add_member(
                        s,
                        household_id=hh.id,
                        email=target.email,
                        role=roles[1],
                        actor=admin,
                    )
            await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Step-up auth tests
# ---------------------------------------------------------------------------


async def test_step_up_auth_with_correct_password(session: AsyncSession) -> None:
    admin = await service.create_user(
        session,
        email="stepup@example.com",
        display_name="StepUp",
        password="stepuppw1",
        is_app_admin=True,
    )
    step_up_token = await service.step_up_auth(
        session,
        user=admin,
        password="stepuppw1",
        totp_code=None,
        jwt_secret=_JWT_SECRET,
    )
    from app.security import jwt as jwt_service

    claims = jwt_service.validate_access_token(step_up_token, _JWT_SECRET)
    assert jwt_service.has_step_up(claims) is True


async def test_step_up_auth_wrong_password_raises(session: AsyncSession) -> None:
    admin = await service.create_user(
        session,
        email="stepup2@example.com",
        display_name="StepUp2",
        password="stepuppw2",
        is_app_admin=True,
    )
    with pytest.raises(service.AuthenticationError):
        await service.step_up_auth(
            session,
            user=admin,
            password="wrong",
            totp_code=None,
            jwt_secret=_JWT_SECRET,
        )


# ---------------------------------------------------------------------------
# RefreshToken helper unit tests (no DB needed)
# ---------------------------------------------------------------------------


def test_refresh_token_hash_is_deterministic() -> None:
    raw = "some-opaque-token"
    h1 = RefreshToken.hash_token(raw)
    h2 = RefreshToken.hash_token(raw)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex is 64 chars


def test_refresh_token_generate_raw_is_unique() -> None:
    t1 = RefreshToken.generate_raw()
    t2 = RefreshToken.generate_raw()
    assert t1 != t2
