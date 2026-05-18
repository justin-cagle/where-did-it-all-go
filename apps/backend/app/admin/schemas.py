"""Pydantic schemas for the admin domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.admin.enums import BackupStatus, BackupTrigger, NotificationType
from app.households.enums import HouseholdRole

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class AdminNotificationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    notification_type: NotificationType
    title: str
    body: str
    entity_id: uuid.UUID | None
    read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListOut(BaseModel):
    items: list[AdminNotificationOut]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


class SMTPConfigIn(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    from_address: str
    use_tls: bool = True


class SMTPConfigOut(BaseModel):
    id: uuid.UUID
    host: str
    port: int
    username: str
    from_address: str
    use_tls: bool
    configured_at: datetime
    smtp_configured: bool
    last_test_success: bool | None
    last_test_error: str | None
    last_test_at: datetime | None


class SMTPTestResult(BaseModel):
    success: bool
    error_detail: str | None


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


class BackupConfigIn(BaseModel):
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_path_prefix: str = "wdiag-backups"
    local_retention_days: int = 30
    s3_enabled: bool = False


class BackupConfigOut(BaseModel):
    id: uuid.UUID
    s3_endpoint: str | None
    s3_bucket: str | None
    s3_access_key: str | None
    s3_path_prefix: str
    local_retention_days: int
    s3_enabled: bool
    configured_at: datetime


class BackupRunOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: BackupStatus
    size_bytes: int | None
    local_path: str | None
    s3_path: str | None
    error_detail: str | None
    triggered_by: BackupTrigger
    triggered_by_id: uuid.UUID | None


class BackupRunListOut(BaseModel):
    items: list[BackupRunOut]
    next_cursor: str | None


class BackupTriggerOut(BaseModel):
    backup_run_id: uuid.UUID


class S3TestResult(BaseModel):
    success: bool
    error_detail: str | None


# ---------------------------------------------------------------------------
# Read-only state
# ---------------------------------------------------------------------------


class ReadOnlyStateOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    enabled: bool
    reason: str | None
    enabled_at: datetime | None
    enabled_by_id: uuid.UUID | None


class SetReadOnlyIn(BaseModel):
    enabled: bool
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def reason_required_when_enabled(cls, v: str | None, info: object) -> str | None:
        data = info.data if hasattr(info, "data") else {}  # type: ignore[union-attr]
        if data.get("enabled") and (v is None or len(v) < 10):
            raise ValueError("reason must be at least 10 characters when enabling read-only mode")
        return v


# ---------------------------------------------------------------------------
# Registration settings
# ---------------------------------------------------------------------------


class RegistrationSettingsOut(BaseModel):
    allow_registration: bool
    registration_limit: int | None
    unassigned_account_ttl_days: int


class RegistrationSettingsIn(BaseModel):
    allow_registration: bool
    registration_limit: int | None = None
    unassigned_account_ttl_days: int = 7


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_app_admin: bool
    created_at: datetime
    household_count: int


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    next_cursor: str | None


class AssignHouseholdIn(BaseModel):
    household_id: uuid.UUID
    role: HouseholdRole = HouseholdRole.MEMBER


class ForceLogoutAllIn(BaseModel):
    confirm: str

    @field_validator("confirm")
    @classmethod
    def confirm_must_match(cls, v: str) -> str:
        if v != "LOGOUT_ALL":
            raise ValueError('confirm must be "LOGOUT_ALL"')
        return v


# ---------------------------------------------------------------------------
# System overview
# ---------------------------------------------------------------------------


class SystemOverviewOut(BaseModel):
    active_user_count: int
    unassigned_user_count: int
    household_count: int
    worker_fast_healthy: bool
    worker_slow_healthy: bool
    pending_job_count: int
    failed_job_count_24h: int
    db_size_bytes: int
    redis_memory_bytes: int
    last_backup: BackupRunOut | None
    smtp_configured: bool
    allow_registration: bool
    registration_limit: int | None
    active_count_vs_limit: str
    alembic_current: str
    alembic_head: str
    alembic_up_to_date: bool
    active_session_count: int
    app_started_at: datetime


class FailedJobOut(BaseModel):
    job_id: str
    function: str
    enqueue_time: str
    score: float


class SystemDetailOut(SystemOverviewOut):
    failed_jobs: list[FailedJobOut]
    table_row_counts: dict[str, int]
    redis_connected_clients: int
    redis_db_keys: int


# ---------------------------------------------------------------------------
# Households (admin view)
# ---------------------------------------------------------------------------


class AdminHouseholdOut(BaseModel):
    id: uuid.UUID
    name: str
    member_count: int
    account_count: int
    created_at: datetime
    visibility_mode: str


class AdminHouseholdListOut(BaseModel):
    items: list[AdminHouseholdOut]


class AdminHouseholdDetailOut(AdminHouseholdOut):
    members: list[AdminUserOut]
