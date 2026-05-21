"""Invitation service for the households domain.

All invitation business logic lives here. Email delivery never raises —
failures are recorded in email_error and surfaced via email_sent=False.
"""

from __future__ import annotations

import secrets
import smtplib
import uuid
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service as admin_service
from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.config import get_settings, smtp_configured
from app.households.enums import HouseholdRole, InvitationStatus
from app.households.models import Household, HouseholdInvitation, HouseholdMembership, User

_INVITE_TTL = timedelta(hours=72)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AlreadyMemberError(Exception):
    """Invitee is already a member of this household."""


class PendingInviteExistsError(Exception):
    """A pending invite for this email + household already exists."""


class InviteNotFoundError(Exception):
    """No invitation found for the given token."""


class InviteExpiredError(Exception):
    """Invitation has expired."""


class AlreadyAcceptedError(Exception):
    """Invitation was already accepted."""


class InviteRevokedError(Exception):
    """Invitation has been revoked."""


class EmailMismatchError(Exception):
    """Authenticated user's email does not match invited_email."""


class PermissionError(Exception):
    """Caller lacks owner or app_admin role."""


class NotFoundError(Exception):
    """Invitation not found by ID."""


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def create_invitation(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    invited_by_id: uuid.UUID,
    invited_email: str,
    role: HouseholdRole,
) -> HouseholdInvitation:
    """Create an invitation and attempt email delivery.

    Raises:
        AlreadyMemberError: invitee is already a member
        PendingInviteExistsError: a pending invite exists for this email + household
    """
    email_lower = invited_email.lower().strip()

    # Check not already a member
    existing_member = await _find_membership_by_email(session, household_id, email_lower)
    if existing_member is not None:
        raise AlreadyMemberError(f"{email_lower!r} is already a member")

    # Check no pending invite
    existing_invite = await _find_pending_invite(session, household_id, email_lower)
    if existing_invite is not None:
        raise PendingInviteExistsError(f"a pending invite already exists for {email_lower!r}")

    now = datetime.now(tz=UTC)
    token = secrets.token_urlsafe(32)
    invite = HouseholdInvitation(
        household_id=household_id,
        invited_email=email_lower,
        invited_by_id=invited_by_id,
        role=str(role),
        token=token,
        status=str(InvitationStatus.PENDING),
        expires_at=now + _INVITE_TTL,
        email_sent=False,
    )
    session.add(invite)
    await session.flush()

    # Attempt email delivery — never raises
    db_smtp = await admin_service.smtp_configured(session)
    if db_smtp or smtp_configured():
        household = await session.get(Household, household_id)
        inviter = await session.get(User, invited_by_id)
        hh_name = household.name if household else "the household"
        inviter_name = inviter.display_name if inviter else "Someone"
        if db_smtp:
            subject = f"{inviter_name} invited you to join {hh_name} on WDIAG"
            body_text = (
                f"{inviter_name} has invited you to join their household "
                f'"{hh_name}" on WDIAG - Where Did It All Go.\n\n'
                f"Accept this invitation:\n{get_invite_url(token)}\n\n"
                f"This link expires in 72 hours and can only be used once.\n\n"
                f"If you don't have a WDIAG account, you'll be prompted to create one "
                f"with this email address ({email_lower}). You can update your email "
                f"after joining in Settings -> Profile.\n\n"
                f"If you weren't expecting this invitation, you can ignore this email."
            )
            sent, error = await admin_service.send_email(
                session,
                to=email_lower,
                subject=subject,
                body_text=body_text,
                body_html=body_text.replace("\n", "<br>"),
            )
        else:
            sent, error = await _send_invite_email(
                to_address=email_lower,
                inviter_name=inviter_name,
                household_name=hh_name,
                invite_url=get_invite_url(token),
            )
        invite.email_sent = sent
        invite.email_error = error
        if sent:
            invite.email_sent_at = datetime.now(tz=UTC)
        await session.flush()

    await _write_audit(
        session,
        actor_id=invited_by_id,
        household_id=household_id,
        entity_id=invite.id,
        operation=AuditOperation.CREATE,
        delta=[
            {"op": "add", "path": "/invited_email", "value": email_lower},
            {"op": "add", "path": "/role", "value": str(role)},
        ],
    )
    return invite


async def get_invite_by_token(
    session: AsyncSession,
    token: str,
) -> HouseholdInvitation:
    """Fetch invitation by token. Auto-expires if past expires_at.

    Raises InviteNotFoundError if not found.
    """
    stmt = sa.select(HouseholdInvitation).where(HouseholdInvitation.token == token)
    result = await session.execute(stmt)
    invite = result.scalar_one_or_none()
    if invite is None:
        raise InviteNotFoundError("invitation not found")

    now = datetime.now(tz=UTC)
    if invite.status == str(InvitationStatus.PENDING) and invite.expires_at < now:
        invite.status = str(InvitationStatus.EXPIRED)
        await session.flush()

    return invite


async def accept_invite(
    session: AsyncSession,
    *,
    token: str,
    user_id: uuid.UUID,
) -> HouseholdMembership:
    """Accept an invitation. Creates HouseholdMembership.

    Raises InviteExpiredError, AlreadyAcceptedError, InviteRevokedError,
    EmailMismatchError, AlreadyMemberError on failures.
    """
    invite = await get_invite_by_token(session, token)

    if invite.status == str(InvitationStatus.EXPIRED):
        raise InviteExpiredError("invitation has expired")
    if invite.status == str(InvitationStatus.ACCEPTED):
        raise AlreadyAcceptedError("invitation already accepted")
    if invite.status == str(InvitationStatus.REVOKED):
        raise InviteRevokedError("invitation has been revoked")

    user = await session.get(User, user_id)
    if user is None:
        raise InviteNotFoundError("user not found")

    if user.email.lower() != invite.invited_email.lower():
        raise EmailMismatchError(
            f"this invite was sent to {invite.invited_email!r}, you are logged in as {user.email!r}"
        )

    existing = await _get_membership(session, invite.household_id, user_id)
    if existing is not None:
        raise AlreadyMemberError("user is already a member of this household")

    membership = HouseholdMembership(
        household_id=invite.household_id,
        user_id=user_id,
        role=invite.role,
    )
    session.add(membership)

    now = datetime.now(tz=UTC)
    invite.status = str(InvitationStatus.ACCEPTED)
    invite.accepted_by_id = user_id
    invite.accepted_at = now
    await session.flush()

    await _write_audit(
        session,
        actor_id=user_id,
        household_id=invite.household_id,
        entity_id=invite.id,
        operation=AuditOperation.UPDATE,
        delta=[
            {"op": "replace", "path": "/status", "value": "accepted"},
            {"op": "add", "path": "/accepted_by_id", "value": str(user_id)},
        ],
    )
    return membership


async def decline_invite(
    session: AsyncSession,
    *,
    token: str,
    user_id: uuid.UUID,
) -> None:
    """Decline an invitation. No email match required."""
    invite = await get_invite_by_token(session, token)

    if invite.status == str(InvitationStatus.EXPIRED):
        raise InviteExpiredError("invitation has expired")
    if invite.status == str(InvitationStatus.ACCEPTED):
        raise AlreadyAcceptedError("invitation already accepted")
    if invite.status == str(InvitationStatus.REVOKED):
        raise InviteRevokedError("invitation has been revoked")

    invite.status = str(InvitationStatus.DECLINED)
    await session.flush()

    await _write_audit(
        session,
        actor_id=user_id,
        household_id=invite.household_id,
        entity_id=invite.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/status", "value": "declined"}],
    )


async def revoke_invite(
    session: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    revoked_by_id: uuid.UUID,
    actor_is_owner: bool,
    actor_is_app_admin: bool,
) -> HouseholdInvitation:
    """Revoke a pending invitation. Caller must be owner or app_admin.

    Raises PermissionError, NotFoundError.
    """
    if not (actor_is_owner or actor_is_app_admin):
        raise PermissionError("must be household owner or app admin to revoke invitations")

    invite = await session.get(HouseholdInvitation, invitation_id)
    if invite is None:
        raise NotFoundError("invitation not found")

    invite.status = str(InvitationStatus.REVOKED)
    await session.flush()

    await _write_audit(
        session,
        actor_id=revoked_by_id,
        household_id=invite.household_id,
        entity_id=invite.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/status", "value": "revoked"}],
    )
    return invite


async def resend_invite(
    session: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    resent_by_id: uuid.UUID,
    actor_is_owner: bool,
    actor_is_app_admin: bool,
) -> HouseholdInvitation:
    """Reset expiry and reattempt email delivery.

    Raises PermissionError, NotFoundError, or InviteExpiredError (if not pending).
    """
    if not (actor_is_owner or actor_is_app_admin):
        raise PermissionError("must be household owner or app admin to resend invitations")

    invite = await session.get(HouseholdInvitation, invitation_id)
    if invite is None:
        raise NotFoundError("invitation not found")

    if invite.status != str(InvitationStatus.PENDING):
        raise InviteExpiredError(
            f"can only resend pending invitations; current status: {invite.status}"
        )

    now = datetime.now(tz=UTC)
    invite.expires_at = now + _INVITE_TTL

    db_smtp = await admin_service.smtp_configured(session)
    if db_smtp or smtp_configured():
        household = await session.get(Household, invite.household_id)
        resender = await session.get(User, resent_by_id)
        hh_name = household.name if household else "the household"
        resender_name = resender.display_name if resender else "Someone"
        if db_smtp:
            subject = f"{resender_name} invited you to join {hh_name} on WDIAG"
            body_text = (
                f"{resender_name} has invited you to join their household "
                f'"{hh_name}" on WDIAG - Where Did It All Go.\n\n'
                f"Accept this invitation:\n{get_invite_url(invite.token)}\n\n"
                f"This link expires in 72 hours and can only be used once.\n\n"
                f"If you don't have a WDIAG account, you'll be prompted to create one "
                f"with this email address ({invite.invited_email}). You can update your email "
                f"after joining in Settings -> Profile.\n\n"
                f"If you weren't expecting this invitation, you can ignore this email."
            )
            sent, error = await admin_service.send_email(
                session,
                to=invite.invited_email,
                subject=subject,
                body_text=body_text,
                body_html=body_text.replace("\n", "<br>"),
            )
        else:
            sent, error = await _send_invite_email(
                to_address=invite.invited_email,
                inviter_name=resender_name,
                household_name=hh_name,
                invite_url=get_invite_url(invite.token),
            )
        invite.email_sent = sent
        invite.email_error = error
        if sent:
            invite.email_sent_at = datetime.now(tz=UTC)
    await session.flush()

    await _write_audit(
        session,
        actor_id=resent_by_id,
        household_id=invite.household_id,
        entity_id=invite.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/expires_at", "value": invite.expires_at.isoformat()}],
    )
    return invite


async def expire_stale_invites(session: AsyncSession) -> int:
    """Bulk-expire all pending invitations past expires_at. Returns count."""
    now = datetime.now(tz=UTC)
    stmt = (
        sa.update(HouseholdInvitation)
        .where(
            HouseholdInvitation.status == str(InvitationStatus.PENDING),
            HouseholdInvitation.expires_at < now,
        )
        .values(status=str(InvitationStatus.EXPIRED))
        .returning(HouseholdInvitation.id)
    )
    result = await session.execute(stmt)
    rows = result.fetchall()
    return len(rows)


async def list_invitations(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    status: InvitationStatus | None = None,
) -> list[HouseholdInvitation]:
    """List invitations for a household, optionally filtered by status."""
    stmt = (
        sa.select(HouseholdInvitation)
        .where(HouseholdInvitation.household_id == household_id)
        .order_by(HouseholdInvitation.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(HouseholdInvitation.status == str(status))
    result = await session.execute(stmt)
    return list(result.scalars().all())


def get_invite_url(token: str) -> str:
    """Construct the invite link using APP_BASE_URL from config."""
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/invite/{token}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _find_membership_by_email(
    session: AsyncSession,
    household_id: uuid.UUID,
    email: str,
) -> HouseholdMembership | None:
    stmt = (
        sa.select(HouseholdMembership)
        .join(User, User.id == HouseholdMembership.user_id)
        .where(
            HouseholdMembership.household_id == household_id,
            User.email == email.lower(),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _find_pending_invite(
    session: AsyncSession,
    household_id: uuid.UUID,
    email: str,
) -> HouseholdInvitation | None:
    stmt = sa.select(HouseholdInvitation).where(
        HouseholdInvitation.household_id == household_id,
        HouseholdInvitation.invited_email == email.lower(),
        HouseholdInvitation.status == str(InvitationStatus.PENDING),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_membership(
    session: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> HouseholdMembership | None:
    stmt = sa.select(HouseholdMembership).where(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == user_id,
        HouseholdMembership.archived_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _send_invite_email(
    *,
    to_address: str,
    inviter_name: str,
    household_name: str,
    invite_url: str,
) -> tuple[bool, str | None]:
    """Attempt SMTP delivery. Returns (sent, error_str|None). Never raises."""
    settings = get_settings()
    try:
        subject = f"{inviter_name} invited you to join {household_name} on WDIAG"
        plain_body = (
            f"{inviter_name} has invited you to join their household "
            f'"{household_name}" on WDIAG - Where Did It All Go.\n\n'
            f"Accept this invitation:\n{invite_url}\n\n"
            f"This link expires in 72 hours and can only be used once.\n\n"
            f"If you don't have a WDIAG account, you'll be prompted to create one "
            f"with this email address ({to_address}). You can update your email "
            f"after joining in Settings -> Profile.\n\n"
            f"If you weren't expecting this invitation, you can ignore this email."
        )
        html_body = plain_body.replace("\n", "<br>")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_address or ""
        msg["To"] = to_address
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        host = settings.smtp_host or ""
        port = settings.smtp_port

        if settings.smtp_use_tls:
            with smtplib.SMTP_SSL(host, port) as smtp:
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(msg["From"], [to_address], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(msg["From"], [to_address], msg.as_string())

        return True, None
    except Exception as exc:
        return False, str(exc)


async def _write_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    household_id: uuid.UUID,
    entity_id: uuid.UUID,
    operation: AuditOperation,
    delta: list[dict[str, Any]],
) -> None:
    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="user_action",
        entity_type="household_invitation",
        entity_id=entity_id,
        operation=operation,
        delta=delta,
        actor_id=actor_id,
    )
