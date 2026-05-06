"""Pydantic schemas for the ingest module API."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SyncConfigCreate(BaseModel):
    account_id: uuid.UUID
    provider: str = Field(..., pattern="^(simplefin|ofx|csv|manual)$")
    credentials: dict[str, Any] = Field(default_factory=dict)
    sync_enabled: bool = True


class SyncConfigOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    provider: str
    sync_enabled: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TriggerResponse(BaseModel):
    import_job_id: uuid.UUID


class UploadResponse(BaseModel):
    import_job_id: uuid.UUID


class ImportJobOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    source: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    row_count: int
    imported_count: int
    duplicate_count: int
    error_count: int
    error_detail: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
