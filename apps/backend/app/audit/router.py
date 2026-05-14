"""FastAPI routes for the audit module.

All routes are scoped under /api/v1/households/{household_id}/audit/.
Requires Owner role or App Admin — Members get 403.

Routes:
  GET  /                                      paginated household log
  GET  /entities/{entity_type}/{entity_id}    full history for one entity
  GET  /entities/{entity_type}/{entity_id}/state  reconstructed state
  GET  /{event_id}/reversals                  reversal chain for an event
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.deps import HouseholdOwnerOrAdmin
from app.audit.models import AuditOperation
from app.audit.schemas import AuditEventOut, AuditLogPage, ReconstructedState
from app.database import get_db

router = APIRouter(tags=["audit"])

_DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/households/{household_id}/audit/",
    response_model=AuditLogPage,
)
async def list_household_audit_log(
    household_id: HouseholdOwnerOrAdmin,
    session: _DbSession,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    operation: AuditOperation | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> AuditLogPage:
    """Paginated audit log for the household, newest first."""
    items, next_cursor = await audit_service.get_household_log(
        session,
        household_id,
        from_dt=from_dt,
        to_dt=to_dt,
        actor_id=actor_id,
        entity_type=entity_type,
        operation=operation,
        limit=limit,
        cursor=cursor,
    )
    return AuditLogPage(
        items=[AuditEventOut.model_validate(e) for e in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/households/{household_id}/audit/entities/{entity_type}/{entity_id}",
    response_model=list[AuditEventOut],
)
async def get_entity_audit_history(
    household_id: HouseholdOwnerOrAdmin,
    entity_type: str,
    entity_id: uuid.UUID,
    session: _DbSession,
) -> list[AuditEventOut]:
    """Full audit history for a specific entity, oldest first."""
    events = await audit_service.get_entity_history(session, entity_type, entity_id, household_id)
    return [AuditEventOut.model_validate(e) for e in events]


@router.get(
    "/households/{household_id}/audit/entities/{entity_type}/{entity_id}/state",
    response_model=ReconstructedState,
)
async def get_entity_reconstructed_state(
    household_id: HouseholdOwnerOrAdmin,
    entity_type: str,
    entity_id: uuid.UUID,
    session: _DbSession,
    as_of: datetime | None = None,
) -> ReconstructedState:
    """Reconstruct entity state by replaying RFC 6902 patches from the audit log."""
    result = await audit_service.reconstruct_state(
        session, entity_type, entity_id, household_id, as_of=as_of
    )
    return ReconstructedState(
        entity_type=entity_type,
        entity_id=entity_id,
        as_of=as_of,
        state=result["state"],
        errors=result["errors"],
    )


@router.get(
    "/households/{household_id}/audit/{event_id}/reversals",
    response_model=list[AuditEventOut],
)
async def get_reversal_chain(
    household_id: HouseholdOwnerOrAdmin,
    event_id: uuid.UUID,
    session: _DbSession,
) -> list[AuditEventOut]:
    """Return the root event and all reversal events linked via source_event_id."""
    chain = await audit_service.get_reversal_chain(session, event_id, household_id)
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="audit event not found",
        )
    return [AuditEventOut.model_validate(e) for e in chain]
