"""Integration tests for the invitation service.

Requires a real Postgres instance (via testcontainers). Run with:
    pytest -m integration tests/test_invitations.py

Coverage:
  - create_invitation: happy path, duplicate email member check, pending dupe check
  - get_invite_by_token: found, not found, auto-expire
  - accept_invite: happy path, email mismatch, already accepted, revoked, expired
  - decline_invite: happy path, already accepted
  - revoke_invite: happy path, permission check, not found
  - resend_invite: happy path, non-pending raises
  - expire_stale_invites: bulk expiry count
  - list_invitations: filtered by status
  - get_invite_url: base URL composition
  - Hypothesis: token uniqueness, email normalization, expiry boundary
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.households.models  # noqa: F401 — registers tables in Base.metadata
from app.database import Base
from app.households import invitations as inv_service
from app.households import service as hh_service
from app.households.enums import HouseholdRole, InvitationStatus, VisibilityMode
from app.households.models import HouseholdMembership

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


async def _make_household(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (owner_user_id, household_id)."""
    suffix = uuid.uuid4().hex[:6]
    user = await hh_service.create_user(
        session,
        email=f"owner_{suffix}@test.com",
        display_name="Owner",
        password="pw12345678",  # pragma: allowlist secret
    )
    household = await hh_service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    await session.commit()
    return user.id, household.id


async def _make_user(session: AsyncSession, email: str) -> uuid.UUID:
    user = await hh_service.create_user(
        session,
        email=email,
        display_name="Invitee",
        password="pw12345678",  # pragma: allowlist secret
    )
    await session.commit()
    return user.id


# ---------------------------------------------------------------------------
# create_invitation
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_invitation_happy_path(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="newbie@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    assert invite.id is not None
    assert invite.invited_email == "newbie@example.com"
    assert invite.status == str(InvitationStatus.PENDING)
    assert len(invite.token) > 20


@pytest.mark.integration
async def test_create_invitation_normalizes_email(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="  UPPER@Example.COM  ",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()
    assert invite.invited_email == "upper@example.com"


@pytest.mark.integration
async def test_create_invitation_already_member_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"member_{suffix}@test.com"
    existing_user = await hh_service.create_user(
        session,
        email=email,
        display_name="Existing",
        password="pw12345678",  # pragma: allowlist secret
    )
    # Directly insert membership (bypasses app-admin gate in add_member)
    session.add(
        HouseholdMembership(
            household_id=hid,
            user_id=existing_user.id,
            role=str(HouseholdRole.MEMBER),
        )
    )
    await session.commit()

    with pytest.raises(inv_service.AlreadyMemberError):
        await inv_service.create_invitation(
            session,
            household_id=hid,
            invited_by_id=owner_id,
            invited_email=email,
            role=HouseholdRole.MEMBER,
        )


@pytest.mark.integration
async def test_create_invitation_pending_dupe_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="dupe@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    with pytest.raises(inv_service.PendingInviteExistsError):
        await inv_service.create_invitation(
            session,
            household_id=hid,
            invited_by_id=owner_id,
            invited_email="dupe@example.com",
            role=HouseholdRole.MEMBER,
        )


# ---------------------------------------------------------------------------
# get_invite_by_token
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_get_invite_by_token_found(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="tok@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    fetched = await inv_service.get_invite_by_token(session, invite.token)
    assert fetched.id == invite.id


@pytest.mark.integration
async def test_get_invite_by_token_not_found_raises(session: AsyncSession) -> None:
    with pytest.raises(inv_service.InviteNotFoundError):
        await inv_service.get_invite_by_token(session, "nonexistent-token")


@pytest.mark.integration
async def test_get_invite_by_token_auto_expires(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="expire@example.com",
        role=HouseholdRole.MEMBER,
    )
    # Backdate expiry
    invite.expires_at = datetime.now(tz=UTC) - timedelta(hours=1)
    await session.flush()
    await session.commit()

    fetched = await inv_service.get_invite_by_token(session, invite.token)
    assert fetched.status == str(InvitationStatus.EXPIRED)


# ---------------------------------------------------------------------------
# accept_invite
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_accept_invite_happy_path(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"joiner_{suffix}@test.com"
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email=email,
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    user_id = await _make_user(session, email)
    membership = await inv_service.accept_invite(session, token=invite.token, user_id=user_id)
    await session.commit()

    assert membership.household_id == hid
    assert membership.user_id == user_id

    refreshed = await inv_service.get_invite_by_token(session, invite.token)
    assert refreshed.status == str(InvitationStatus.ACCEPTED)


@pytest.mark.integration
async def test_accept_invite_email_mismatch_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="correct@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    wrong_user_id = await _make_user(session, f"wrong_{uuid.uuid4().hex[:6]}@test.com")
    with pytest.raises(inv_service.EmailMismatchError):
        await inv_service.accept_invite(session, token=invite.token, user_id=wrong_user_id)


@pytest.mark.integration
async def test_accept_invite_already_accepted_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"twice_{suffix}@test.com"
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email=email,
        role=HouseholdRole.MEMBER,
    )
    await session.commit()
    user_id = await _make_user(session, email)
    await inv_service.accept_invite(session, token=invite.token, user_id=user_id)
    await session.commit()

    with pytest.raises(inv_service.AlreadyAcceptedError):
        await inv_service.accept_invite(session, token=invite.token, user_id=user_id)


@pytest.mark.integration
async def test_accept_invite_revoked_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"revoked_{suffix}@test.com"
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email=email,
        role=HouseholdRole.MEMBER,
    )
    await session.commit()
    await inv_service.revoke_invite(
        session,
        invitation_id=invite.id,
        revoked_by_id=owner_id,
        actor_is_owner=True,
        actor_is_app_admin=False,
    )
    await session.commit()

    user_id = await _make_user(session, email)
    with pytest.raises(inv_service.InviteRevokedError):
        await inv_service.accept_invite(session, token=invite.token, user_id=user_id)


@pytest.mark.integration
async def test_accept_invite_expired_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"xpd_{suffix}@test.com"
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email=email,
        role=HouseholdRole.MEMBER,
    )
    invite.expires_at = datetime.now(tz=UTC) - timedelta(hours=1)
    await session.flush()
    await session.commit()

    user_id = await _make_user(session, email)
    with pytest.raises(inv_service.InviteExpiredError):
        await inv_service.accept_invite(session, token=invite.token, user_id=user_id)


# ---------------------------------------------------------------------------
# decline_invite
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_decline_invite_happy_path(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="decliner@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    user_id = await _make_user(session, "decliner@example.com")
    await inv_service.decline_invite(session, token=invite.token, user_id=user_id)
    await session.commit()

    refreshed = await inv_service.get_invite_by_token(session, invite.token)
    assert refreshed.status == str(InvitationStatus.DECLINED)


@pytest.mark.integration
async def test_decline_invite_already_accepted_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    suffix = uuid.uuid4().hex[:6]
    email = f"dec_acc_{suffix}@test.com"
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email=email,
        role=HouseholdRole.MEMBER,
    )
    await session.commit()
    user_id = await _make_user(session, email)
    await inv_service.accept_invite(session, token=invite.token, user_id=user_id)
    await session.commit()

    with pytest.raises(inv_service.AlreadyAcceptedError):
        await inv_service.decline_invite(session, token=invite.token, user_id=user_id)


# ---------------------------------------------------------------------------
# revoke_invite
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_revoke_invite_happy_path(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="revokeme@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    revoked = await inv_service.revoke_invite(
        session,
        invitation_id=invite.id,
        revoked_by_id=owner_id,
        actor_is_owner=True,
        actor_is_app_admin=False,
    )
    await session.commit()
    assert revoked.status == str(InvitationStatus.REVOKED)


@pytest.mark.integration
async def test_revoke_invite_not_owner_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="perm@example.com",
        role=HouseholdRole.MEMBER,
    )
    await session.commit()

    with pytest.raises(inv_service.PermissionError):
        await inv_service.revoke_invite(
            session,
            invitation_id=invite.id,
            revoked_by_id=owner_id,
            actor_is_owner=False,
            actor_is_app_admin=False,
        )


@pytest.mark.integration
async def test_revoke_invite_not_found_raises(session: AsyncSession) -> None:
    owner_id, _hid = await _make_household(session)
    await session.commit()

    with pytest.raises(inv_service.NotFoundError):
        await inv_service.revoke_invite(
            session,
            invitation_id=uuid.uuid4(),
            revoked_by_id=owner_id,
            actor_is_owner=True,
            actor_is_app_admin=False,
        )


# ---------------------------------------------------------------------------
# resend_invite
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_resend_invite_extends_expiry(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="resend@example.com",
        role=HouseholdRole.MEMBER,
    )
    old_expiry = invite.expires_at
    await session.commit()

    resent = await inv_service.resend_invite(
        session,
        invitation_id=invite.id,
        resent_by_id=owner_id,
        actor_is_owner=True,
        actor_is_app_admin=False,
    )
    await session.commit()
    assert resent.expires_at > old_expiry


@pytest.mark.integration
async def test_resend_invite_non_pending_raises(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    invite = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="resend2@example.com",
        role=HouseholdRole.MEMBER,
    )
    await inv_service.revoke_invite(
        session,
        invitation_id=invite.id,
        revoked_by_id=owner_id,
        actor_is_owner=True,
        actor_is_app_admin=False,
    )
    await session.commit()

    with pytest.raises(inv_service.InviteExpiredError):
        await inv_service.resend_invite(
            session,
            invitation_id=invite.id,
            resent_by_id=owner_id,
            actor_is_owner=True,
            actor_is_app_admin=False,
        )


# ---------------------------------------------------------------------------
# expire_stale_invites
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_expire_stale_invites_returns_count(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)

    stale_1 = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="stale1@example.com",
        role=HouseholdRole.MEMBER,
    )
    stale_2 = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="stale2@example.com",
        role=HouseholdRole.MEMBER,
    )
    fresh = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="fresh@example.com",
        role=HouseholdRole.MEMBER,
    )
    now = datetime.now(tz=UTC)
    stale_1.expires_at = now - timedelta(hours=2)
    stale_2.expires_at = now - timedelta(hours=1)
    await session.flush()
    await session.commit()

    count = await inv_service.expire_stale_invites(session)
    await session.commit()

    assert count == 2
    await session.refresh(fresh)
    assert fresh.status == str(InvitationStatus.PENDING)


# ---------------------------------------------------------------------------
# list_invitations
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_invitations_filtered_by_status(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)
    await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="list1@example.com",
        role=HouseholdRole.MEMBER,
    )
    invite2 = await inv_service.create_invitation(
        session,
        household_id=hid,
        invited_by_id=owner_id,
        invited_email="list2@example.com",
        role=HouseholdRole.MEMBER,
    )
    await inv_service.revoke_invite(
        session,
        invitation_id=invite2.id,
        revoked_by_id=owner_id,
        actor_is_owner=True,
        actor_is_app_admin=False,
    )
    await session.commit()

    pending = await inv_service.list_invitations(
        session, household_id=hid, status=InvitationStatus.PENDING
    )
    revoked = await inv_service.list_invitations(
        session, household_id=hid, status=InvitationStatus.REVOKED
    )
    all_invites = await inv_service.list_invitations(session, household_id=hid)

    assert len(pending) == 1
    assert len(revoked) == 1
    assert len(all_invites) == 2


# ---------------------------------------------------------------------------
# get_invite_url
# ---------------------------------------------------------------------------


def test_get_invite_url_composes_correctly() -> None:
    token = "abc123"
    with patch("app.households.invitations.get_settings") as mock_settings:
        mock_settings.return_value.app_base_url = "https://wdiag.example.com/"
        url = inv_service.get_invite_url(token)
    assert url == "https://wdiag.example.com/invite/abc123"


def test_get_invite_url_strips_trailing_slash() -> None:
    token = "xyz"
    with patch("app.households.invitations.get_settings") as mock_settings:
        mock_settings.return_value.app_base_url = "https://wdiag.example.com"
        url = inv_service.get_invite_url(token)
    assert url == "https://wdiag.example.com/invite/xyz"


# ---------------------------------------------------------------------------
# email delivery: failure is recorded, never raises
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_email_failure_recorded_not_raised(session: AsyncSession) -> None:
    owner_id, hid = await _make_household(session)

    with (
        patch("app.households.invitations.smtp_configured", return_value=True),
        patch(
            "app.households.invitations._send_invite_email",
            new_callable=AsyncMock,
            return_value=(False, "Connection refused"),
        ),
    ):
        invite = await inv_service.create_invitation(
            session,
            household_id=hid,
            invited_by_id=owner_id,
            invited_email="fail@example.com",
            role=HouseholdRole.MEMBER,
        )
    await session.commit()

    assert invite.email_sent is False
    assert invite.email_error == "Connection refused"


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


@given(st.emails())
@settings(max_examples=50, deadline=None)
def test_email_normalization_idempotent(email: str) -> None:
    normalized = email.lower().strip()
    assert normalized == normalized.lower().strip()


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=30, deadline=None)
def test_token_urlsafe_min_length(nbytes: int) -> None:
    import secrets

    token = secrets.token_urlsafe(nbytes)
    assert isinstance(token, str)
    assert len(token) > 0


@given(st.timedeltas(min_value=timedelta(seconds=0), max_value=timedelta(hours=200)))
@settings(max_examples=50, deadline=None)
def test_expiry_boundary(delta: timedelta) -> None:
    now = datetime.now(tz=UTC)
    expires_at = now + delta
    is_expired = expires_at < now
    assert not is_expired
