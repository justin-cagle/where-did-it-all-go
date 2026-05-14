"""Pydantic schemas for the audit API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_type: str
    actor_id: uuid.UUID | None
    actor_source: str
    household_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    operation: str
    delta: list[Any]
    rationale: str | None
    source_event_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class AuditLogPage(BaseModel):
    items: list[AuditEventOut]
    next_cursor: str | None


class ReconstructedState(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    as_of: datetime | None
    state: dict[str, Any]
    errors: list[str]
