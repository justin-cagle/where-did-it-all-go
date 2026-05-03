"""FastAPI dependency functions for the transactions module."""

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.database import get_db
from app.households.deps import CurrentUser
from app.households.models import HouseholdMembership


async def _require_household_member(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Verify current_user is an active member of the household."""
    stmt = sa.select(HouseholdMembership).where(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == current_user.id,
        HouseholdMembership.archived_at.is_(None),
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not a member of this household",
        )
    return household_id


HouseholdMember = Annotated[uuid.UUID, Depends(_require_household_member)]


async def _require_account_in_household(
    account_id: uuid.UUID,
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Verify the account belongs to the household (and is not archived)."""
    stmt = sa.select(Account).where(
        Account.id == account_id,
        Account.household_id == household_id,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found in this household",
        )
    return account_id


AccountInHousehold = Annotated[uuid.UUID, Depends(_require_account_in_household)]
