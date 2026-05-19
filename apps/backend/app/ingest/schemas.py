"""Pydantic schemas for the ingest module API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# SyncConfig
# ---------------------------------------------------------------------------


class SyncConfigCreate(BaseModel):
    """Create a SimpleFIN sync configuration.

    For SimpleFIN: supply setup_token (exchanged immediately for access_url) and label.
    setup_token is one-time-use and never stored.
    """

    provider: str = Field(..., pattern="^(simplefin|ofx|csv|manual)$")
    setup_token: str | None = Field(None, description="SimpleFIN one-time setup token")
    label: str | None = Field(None, description="User-assigned display name")
    sync_enabled: bool = True


class SyncConfigUpdate(BaseModel):
    label: str | None = None
    sync_interval_hours: int | None = Field(None, ge=1, le=24)
    sync_enabled: bool | None = None


class SyncConfigOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    provider: str
    label: str | None
    sync_enabled: bool
    last_synced_at: datetime | None
    sync_interval_hours: int
    requests_today: int
    requests_today_reset_at: date | None
    next_sync_at: datetime | None
    last_error: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Import job
# ---------------------------------------------------------------------------


class TriggerResponse(BaseModel):
    import_job_id: uuid.UUID


class UploadResponse(BaseModel):
    import_job_id: uuid.UUID


class ImportJobOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    source: str
    status: str
    filename: str | None
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


# ---------------------------------------------------------------------------
# Preview / mapping
# ---------------------------------------------------------------------------


class SimplefinAccountPreview(BaseModel):
    """One SimpleFIN account returned by the preview endpoint."""

    simplefin_account_id: str
    institution_name: str
    account_name: str
    account_number_last4: str | None
    balance: str
    currency: str
    suggested_type: str


class MappingDecision(BaseModel):
    simplefin_account_id: str
    action: Literal["create", "map", "ignore"]
    system_account_id: uuid.UUID | None = None
    authoritative: bool = True
    new_account: dict[str, Any] | None = None


class MappingResult(BaseModel):
    accounts_created: int
    accounts_mapped: int
    accounts_ignored: int


# ---------------------------------------------------------------------------
# CSV mapping persistence
# ---------------------------------------------------------------------------


class CSVMappingIn(BaseModel):
    institution_name: str
    column_map: dict[str, Any] = Field(default_factory=dict)
    date_format: str | None = None
    amount_convention: str = "positive_is_credit"


class CSVMappingOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    institution_name: str
    column_map: dict[str, Any]
    date_format: str | None
    amount_convention: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Job list
# ---------------------------------------------------------------------------


class ImportJobListOut(BaseModel):
    jobs: list[ImportJobOut]
    total: int


# ---------------------------------------------------------------------------
# Decimal helper
# ---------------------------------------------------------------------------


def decimal_str(v: Decimal) -> str:
    return str(v)
