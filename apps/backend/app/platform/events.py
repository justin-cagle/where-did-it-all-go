"""Lifecycle event callbacks for cross-module coordination.

Modules that own lifecycle events (e.g., households) call fire_* functions.
Downstream modules register callbacks at application startup (in main.py lifespan)
rather than at import time, avoiding circular imports.

This module never imports from any domain module — it only holds typed callbacks.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

HouseholdCreatedCallback = Callable[[AsyncSession, uuid.UUID], Awaitable[None]]

_on_household_created: list[HouseholdCreatedCallback] = []


def register_on_household_created(callback: HouseholdCreatedCallback) -> None:
    """Register a callback to run after a household is created."""
    _on_household_created.append(callback)


async def fire_household_created(session: AsyncSession, household_id: uuid.UUID) -> None:
    """Invoke all registered household-created callbacks in registration order."""
    for callback in _on_household_created:
        await callback(session, household_id)
