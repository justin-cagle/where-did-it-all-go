"""FastAPI dependency functions for the audit module."""

from __future__ import annotations

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.households.enums import HouseholdRole
from app.households.models import HouseholdMembership


async def _require_owner_or_app_admin(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Audit routes require Owner role or App Admin.

    Members get 403 — they may not read the household audit log.
    """
    if current_user.is_app_admin:
        return household_id

    stmt = sa.select(HouseholdMembership).where(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == current_user.id,
        HouseholdMembership.archived_at.is_(None),
        HouseholdMembership.role == str(HouseholdRole.OWNER),
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role or App Admin required",
        )
    return household_id


HouseholdOwnerOrAdmin = Annotated[uuid.UUID, Depends(_require_owner_or_app_admin)]
