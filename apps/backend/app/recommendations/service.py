"""Recommendations service layer.

All cross-module access to recommendations goes through this interface.
No subsystem gets direct DB access to the recommendations tables.

Public interface:
    create(...)                                        -> Recommendation
    get(recommendation_id, household_id)               -> Recommendation
    accept(recommendation_id, household_id, user_id)   -> Recommendation
    reject(recommendation_id, household_id, user_id)   -> Recommendation
    expire_stale()                                     -> list[Recommendation]
    list_pending(household_id, source, target_subsystem, status)
    get_auto_apply_rule(household_id, source)           -> bool
    set_auto_apply(household_id, source, enabled)       -> AutoApplyRule
    should_auto_apply(household_id, source)             -> bool
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import ActorType, AuditEvent, AuditOperation
from app.recommendations.enums import RecommendationSource, RecommendationStatus
from app.recommendations.models import AutoApplyRule, Recommendation

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Recommendation does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a state constraint."""


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


async def create(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: RecommendationSource,
    target_subsystem: str,
    target_entity_id: uuid.UUID | None = None,
    proposed_value: dict[str, Any] | None = None,
    rationale_text: str,
    rationale_data: dict[str, Any] | None = None,
    confidence: Decimal | None = None,
    expires_at: datetime | None = None,
) -> Recommendation:
    """Create a pending Recommendation from any subsystem."""
    rec = Recommendation(
        household_id=household_id,
        source=str(source),
        target_subsystem=target_subsystem,
        target_entity_id=target_entity_id,
        proposed_value=proposed_value or {},
        rationale_text=rationale_text,
        rationale_data=rationale_data or {},
        confidence=confidence,
        status=str(RecommendationStatus.PENDING),
        expires_at=expires_at,
        auto_apply=False,
    )
    session.add(rec)
    await session.flush()
    logger.info(
        "recommendation.created",
        recommendation_id=str(rec.id),
        source=str(source),
        target_subsystem=target_subsystem,
        household_id=str(household_id),
    )
    return rec


async def get(
    session: AsyncSession,
    *,
    recommendation_id: uuid.UUID,
    household_id: uuid.UUID,
) -> Recommendation:
    """Return a recommendation scoped to household. Raises NotFoundError if absent."""
    result = await session.execute(
        sa.select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.household_id == household_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise NotFoundError("recommendation not found")
    return rec


async def accept(
    session: AsyncSession,
    *,
    recommendation_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Recommendation:
    """Accept a pending recommendation.

    Transitions status to accepted. Writes AuditEvent carrying rationale_text
    forward. Returns the accepted Recommendation — caller applies the actual
    change in its own tables.
    """
    rec = await get(session, recommendation_id=recommendation_id, household_id=household_id)
    _assert_pending(rec, "accept")

    now = datetime.now(tz=UTC)
    rec.status = str(RecommendationStatus.ACCEPTED)
    rec.resolved_at = now
    rec.resolved_by = user_id
    await session.flush()

    audit = AuditEvent(
        actor_type=str(ActorType.USER),
        actor_id=user_id,
        actor_source="recommendation_hitl",
        household_id=household_id,
        entity_type="recommendation",
        entity_id=recommendation_id,
        operation=str(AuditOperation.ACCEPT),
        delta=[{"op": "replace", "path": "/status", "value": "accepted"}],
        rationale=rec.rationale_text,
    )
    session.add(audit)
    await session.flush()
    logger.info(
        "recommendation.accepted",
        recommendation_id=str(recommendation_id),
        user_id=str(user_id),
    )
    return rec


async def reject(
    session: AsyncSession,
    *,
    recommendation_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Recommendation:
    """Reject a pending recommendation. Writes AuditEvent."""
    rec = await get(session, recommendation_id=recommendation_id, household_id=household_id)
    _assert_pending(rec, "reject")

    now = datetime.now(tz=UTC)
    rec.status = str(RecommendationStatus.REJECTED)
    rec.resolved_at = now
    rec.resolved_by = user_id
    await session.flush()

    audit = AuditEvent(
        actor_type=str(ActorType.USER),
        actor_id=user_id,
        actor_source="recommendation_hitl",
        household_id=household_id,
        entity_type="recommendation",
        entity_id=recommendation_id,
        operation=str(AuditOperation.REJECT),
        delta=[{"op": "replace", "path": "/status", "value": "rejected"}],
        rationale=rec.rationale_text,
    )
    session.add(audit)
    await session.flush()
    logger.info(
        "recommendation.rejected",
        recommendation_id=str(recommendation_id),
        user_id=str(user_id),
    )
    return rec


async def expire_stale(session: AsyncSession) -> list[Recommendation]:
    """Set status=expired for all pending recommendations past their expires_at.

    Called by daily ARQ sweep job. Idempotent: already-expired rows are skipped.
    Does not write AuditEvents — expiry is a scheduled system sweep, not a user action.
    """
    now = datetime.now(tz=UTC)
    result = await session.execute(
        sa.select(Recommendation).where(
            Recommendation.status == str(RecommendationStatus.PENDING),
            Recommendation.expires_at.is_not(None),
            Recommendation.expires_at < now,
        )
    )
    stale = list(result.scalars().all())
    for rec in stale:
        rec.status = str(RecommendationStatus.EXPIRED)
        rec.resolved_at = now
    if stale:
        await session.flush()
    logger.info("recommendation.expire_stale.complete", expired=len(stale))
    return stale


async def list_pending(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: RecommendationSource | None = None,
    target_subsystem: str | None = None,
    status: RecommendationStatus | None = RecommendationStatus.PENDING,
) -> list[Recommendation]:
    """Return recommendations for the household, optionally filtered."""
    stmt = sa.select(Recommendation).where(Recommendation.household_id == household_id)
    if source is not None:
        stmt = stmt.where(Recommendation.source == str(source))
    if target_subsystem is not None:
        stmt = stmt.where(Recommendation.target_subsystem == target_subsystem)
    if status is not None:
        stmt = stmt.where(Recommendation.status == str(status))
    stmt = stmt.order_by(Recommendation.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Auto-apply
# ---------------------------------------------------------------------------


async def get_auto_apply_rule(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: RecommendationSource,
) -> bool:
    """Return the enabled flag for a source's auto-apply rule. Defaults to False."""
    result = await session.execute(
        sa.select(AutoApplyRule).where(
            AutoApplyRule.household_id == household_id,
            AutoApplyRule.source == str(source),
        )
    )
    rule = result.scalar_one_or_none()
    return rule.enabled if rule is not None else False


async def set_auto_apply(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: RecommendationSource,
    enabled: bool,
) -> AutoApplyRule:
    """Upsert the auto-apply rule for a source. Returns the updated rule."""
    result = await session.execute(
        sa.select(AutoApplyRule).where(
            AutoApplyRule.household_id == household_id,
            AutoApplyRule.source == str(source),
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        rule = AutoApplyRule(
            household_id=household_id,
            source=str(source),
            enabled=enabled,
        )
        session.add(rule)
    else:
        rule.enabled = enabled
    await session.flush()
    logger.info(
        "recommendation.auto_apply.set",
        household_id=str(household_id),
        source=str(source),
        enabled=enabled,
    )
    return rule


async def should_auto_apply(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: RecommendationSource,
) -> bool:
    """Advisory check: should emitting subsystem auto-accept from this source?

    Returns True only when the household has explicitly enabled auto-apply for
    this source. Does NOT accept the recommendation — caller must still call
    accept() explicitly.
    """
    return await get_auto_apply_rule(session, household_id=household_id, source=source)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assert_pending(rec: Recommendation, operation: str) -> None:
    """Raise ConflictError if not pending (accepted/rejected/expired are terminal)."""
    if rec.status != str(RecommendationStatus.PENDING):
        raise ConflictError(
            f"cannot {operation} recommendation with status {rec.status!r}; "
            "only pending recommendations can be accepted or rejected"
        )
