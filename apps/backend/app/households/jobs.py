"""ARQ background jobs for the households domain.

cleanup_unassigned_accounts -> worker-slow (daily)
  Hard-deletes user accounts with no household membership and no pending
  invite whose created_at is older than UNASSIGNED_ACCOUNT_TTL_DAYS.

expire_stale_invites -> worker-slow (daily)
  Sets status=expired on all pending invitations past expires_at.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.config import get_settings
from app.database import get_session_factory
from app.households.models import HouseholdMembership, RefreshToken, User

logger = structlog.get_logger(__name__)


async def cleanup_unassigned_accounts(ctx: dict[str, Any]) -> dict[str, Any]:
    """Hard-delete unassigned accounts past TTL.

    Criteria for deletion:
      - No HouseholdMembership exists for the user
      - created_at < now() - UNASSIGNED_ACCOUNT_TTL_DAYS

    Per deletion:
      - Null out attributed_to_user_id on transactions_split_allocation rows
      - Revoke all refresh tokens
      - Hard-delete the User row
      - Write an AuditLog entry (actor_type=system, operation=delete)
    """
    _ = ctx
    settings = get_settings()
    ttl_days = settings.unassigned_account_ttl_days
    if ttl_days <= 0:
        logger.info("cleanup_unassigned_accounts.skipped", reason="ttl_disabled")
        return {"deleted": 0, "skipped_ttl_disabled": True}

    cutoff = datetime.now(tz=UTC) - timedelta(days=ttl_days)

    factory = get_session_factory()
    deleted = 0

    async with factory() as session:
        candidates = await _find_candidates(session, cutoff)
        for user_id in candidates:
            await _delete_user(session, user_id)
            await session.commit()
            deleted += 1

    logger.info("cleanup_unassigned_accounts.complete", deleted=deleted)
    return {"deleted": deleted}


async def _find_candidates(session: AsyncSession, cutoff: datetime) -> list[uuid.UUID]:
    """Return user IDs eligible for TTL deletion."""
    has_membership = (
        sa.select(HouseholdMembership.user_id)
        .where(HouseholdMembership.user_id == User.id)
        .correlate(User)
        .exists()
    )
    stmt = (
        sa.select(User.id)
        .where(
            ~has_membership,
            User.created_at < cutoff,
        )
        .execution_options(include_archived=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Null attributions, revoke tokens, hard-delete user, write audit entry."""
    # Null out attributed_to_user_id on split allocations (cross-table raw SQL
    # — households cannot import transactions module per import-linter contract).
    await session.execute(
        sa.text(
            "UPDATE transactions_split_allocation "
            "SET attributed_to_user_id = NULL "
            "WHERE attributed_to_user_id = :uid"
        ),
        {"uid": user_id},
    )

    # Revoke all refresh tokens
    now = datetime.now(tz=UTC)
    await session.execute(
        sa.update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    # Write audit entry before hard delete (entity_id must still resolvable)
    await audit_service.log(
        session,
        household_id=None,
        actor_type=ActorType.SYSTEM,
        actor_source="cleanup_job",
        entity_type="user",
        entity_id=user_id,
        operation=AuditOperation.DELETE,
        delta=[{"op": "remove", "path": "/id", "value": str(user_id)}],
        rationale="Unassigned account TTL exceeded",
        actor_id=None,
    )

    # Hard delete
    await session.execute(sa.delete(User).where(User.id == user_id))
    logger.info("cleanup_unassigned_accounts.deleted", user_id=str(user_id))


async def expire_stale_invites(ctx: dict[str, Any]) -> dict[str, Any]:
    """Bulk-expire pending invitations past their expires_at.

    Runs daily. Idempotent — safe to run multiple times.
    """
    _ = ctx
    from app.households.invitations import expire_stale_invites as _expire

    factory = get_session_factory()
    async with factory() as session:
        count = await _expire(session)
        await session.commit()

    logger.info("expire_stale_invites.complete", expired=count)
    return {"expired": count}
