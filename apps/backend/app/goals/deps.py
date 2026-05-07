"""FastAPI dependency functions for the goals module."""

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.households.models import HouseholdMembership


async def _require_household_member(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Verify current_user is an active member of the household."""
    result = await session.execute(
        sa.select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == current_user.id,
            HouseholdMembership.archived_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not a member of this household",
        )
    return household_id


HouseholdMember = Annotated[uuid.UUID, Depends(_require_household_member)]
