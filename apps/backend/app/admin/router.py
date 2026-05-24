"""FastAPI routes for the admin panel.

All routes require is_app_admin=True.
Mutating routes additionally require step-up auth.

Mount at /api/v1/admin/ in main.py.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service
from app.admin.enums import SmtpTlsMode
from app.admin.schemas import (
    AdminHouseholdDetailOut,
    AdminHouseholdListOut,
    AdminHouseholdOut,
    AdminNotificationOut,
    AdminUserListOut,
    AdminUserOut,
    AssignHouseholdIn,
    BackupConfigIn,
    BackupConfigOut,
    BackupRunListOut,
    BackupRunOut,
    BackupTriggerOut,
    ForceLogoutAllIn,
    NotificationListOut,
    ReadOnlyStateOut,
    RegistrationSettingsIn,
    RegistrationSettingsOut,
    S3TestResult,
    SetReadOnlyIn,
    SMTPConfigIn,
    SMTPConfigOut,
    SMTPTestResult,
    SystemDetailOut,
    SystemOverviewOut,
)
from app.database import get_db
from app.households.deps import AppAdmin

router = APIRouter(tags=["admin"])

_DbSession = Annotated[AsyncSession, Depends(get_db)]
_Admin = AppAdmin


# ---------------------------------------------------------------------------
# System overview
# ---------------------------------------------------------------------------


@router.get("/admin/overview", response_model=SystemOverviewOut)
async def get_overview(
    current_admin: _Admin,
    session: _DbSession,
) -> dict[str, Any]:
    from app.platform.app_state import get_started_at

    return await service.get_system_overview(session, get_started_at())


@router.get("/admin/system", response_model=SystemDetailOut)
async def get_system(
    current_admin: _Admin,
    session: _DbSession,
) -> dict[str, Any]:
    from app.platform.app_state import get_started_at

    return await service.get_system_detail(session, get_started_at())


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/admin/users", response_model=AdminUserListOut)
async def list_users(
    current_admin: _Admin,
    session: _DbSession,
    search: Annotated[str | None, Query()] = None,
    unassigned: Annotated[bool | None, Query()] = None,
    is_admin: Annotated[bool | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100)] = 50,
) -> AdminUserListOut:
    rows, next_cursor = await service.list_users(
        session,
        search=search,
        unassigned=unassigned,
        is_admin=is_admin,
        limit=limit,
        cursor=cursor,
    )
    return AdminUserListOut(
        items=[AdminUserOut(**r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/admin/users/{user_id}", response_model=AdminUserOut)
async def get_user(
    user_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> AdminUserOut:
    try:
        row = await service.get_user(session, user_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AdminUserOut(**row)


@router.post("/admin/users/{user_id}/promote", status_code=status.HTTP_204_NO_CONTENT)
async def promote_user(
    user_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.promote_user(session, user_id, by_id=current_admin.id)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/admin/users/{user_id}/demote", status_code=status.HTTP_204_NO_CONTENT)
async def demote_user(
    user_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.demote_user(session, user_id, by_id=current_admin.id)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.LastAdminError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/admin/users/{user_id}/assign-household",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def assign_household(
    user_id: uuid.UUID,
    body: AssignHouseholdIn,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.assign_household(
            session,
            user_id=user_id,
            household_id=body.household_id,
            role=body.role,
            by_id=current_admin.id,
        )
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/admin/users/{user_id}/force-logout", status_code=status.HTTP_204_NO_CONTENT)
async def force_logout(
    user_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    await service.force_logout(session, user_id)
    await session.commit()


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.delete_user(session, user_id=user_id, by_id=current_admin.id)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.LastAdminError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Households (admin view)
# ---------------------------------------------------------------------------


@router.get("/admin/households", response_model=AdminHouseholdListOut)
async def list_households(
    current_admin: _Admin,
    session: _DbSession,
) -> AdminHouseholdListOut:
    rows = await service.list_households_admin(session)
    return AdminHouseholdListOut(items=[AdminHouseholdOut(**r) for r in rows])


@router.get("/admin/households/{household_id}", response_model=AdminHouseholdDetailOut)
async def get_household(
    household_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> AdminHouseholdDetailOut:
    try:
        data = await service.get_household_admin(session, household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    members = [AdminUserOut(**m) for m in data.pop("members")]
    return AdminHouseholdDetailOut(**data, members=members)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@router.get("/admin/notifications", response_model=NotificationListOut)
async def list_notifications(
    current_admin: _Admin,
    session: _DbSession,
    read: Annotated[bool | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=200)] = 50,
) -> NotificationListOut:
    rows, next_cursor = await service.list_notifications(
        session, read=read, limit=limit, cursor=cursor
    )
    return NotificationListOut(
        items=[AdminNotificationOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/admin/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_read(
    notification_id: uuid.UUID,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.mark_read(session, notification_id)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/admin/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    await service.mark_all_read(session)
    await session.commit()


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


@router.get("/admin/smtp", response_model=SMTPConfigOut)
async def get_smtp(
    current_admin: _Admin,
    session: _DbSession,
) -> SMTPConfigOut:
    from app.config import get_settings

    cfg = await service.get_smtp_config(session)
    master_key = get_settings().master_key
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP not configured")
    return SMTPConfigOut(
        id=cfg.id,
        host=service.decrypt_field(cfg.host_enc, master_key),
        port=cfg.port,
        username=service.decrypt_field(cfg.username_enc, master_key),
        from_address=cfg.from_address,
        tls_mode=SmtpTlsMode(cfg.tls_mode),
        configured_at=cfg.configured_at,
        smtp_configured=True,
        last_test_success=cfg.last_test_success,
        last_test_error=cfg.last_test_error,
        last_test_at=cfg.last_test_at,
    )


@router.post("/admin/smtp", response_model=SMTPConfigOut, status_code=status.HTTP_200_OK)
async def upsert_smtp(
    body: SMTPConfigIn,
    current_admin: _Admin,
    session: _DbSession,
) -> SMTPConfigOut:
    cfg = await service.upsert_smtp_config(
        session,
        host=body.host,
        port=body.port,
        username=body.username,
        password=body.password,
        from_address=body.from_address,
        tls_mode=body.tls_mode,
        configured_by_id=current_admin.id,
    )
    await session.commit()
    return SMTPConfigOut(
        id=cfg.id,
        host=body.host,
        port=cfg.port,
        username=body.username,
        from_address=cfg.from_address,
        tls_mode=SmtpTlsMode(cfg.tls_mode),
        configured_at=cfg.configured_at,
        smtp_configured=True,
        last_test_success=cfg.last_test_success,
        last_test_error=cfg.last_test_error,
        last_test_at=cfg.last_test_at,
    )


@router.post("/admin/smtp/test", response_model=SMTPTestResult)
async def test_smtp(
    current_admin: _Admin,
    session: _DbSession,
) -> SMTPTestResult:
    success, error = await service.test_smtp(session, current_admin.email)
    await session.commit()
    return SMTPTestResult(success=success, error_detail=error)


@router.delete("/admin/smtp", status_code=status.HTTP_204_NO_CONTENT)
async def delete_smtp(
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    await service.delete_smtp_config(session)
    await session.commit()


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


@router.get("/admin/backup/config", response_model=BackupConfigOut)
async def get_backup_config(
    current_admin: _Admin,
    session: _DbSession,
) -> BackupConfigOut:
    from app.config import get_settings

    cfg = await service.get_backup_config(session)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup config not found")
    master_key = get_settings().master_key

    def _dec_opt(val: str | None) -> str | None:
        return service.decrypt_field(val, master_key) if val else None

    return BackupConfigOut(
        id=cfg.id,
        s3_endpoint=_dec_opt(cfg.s3_endpoint_enc),
        s3_bucket=cfg.s3_bucket,
        s3_access_key=_dec_opt(cfg.s3_access_key_enc),
        s3_path_prefix=cfg.s3_path_prefix,
        local_retention_days=cfg.local_retention_days,
        s3_enabled=cfg.s3_enabled,
        configured_at=cfg.configured_at,
    )


@router.post(
    "/admin/backup/config",
    response_model=BackupConfigOut,
    status_code=status.HTTP_200_OK,
)
async def upsert_backup_config(
    body: BackupConfigIn,
    current_admin: _Admin,
    session: _DbSession,
) -> BackupConfigOut:
    cfg = await service.upsert_backup_config(
        session,
        s3_endpoint=body.s3_endpoint,
        s3_bucket=body.s3_bucket,
        s3_access_key=body.s3_access_key,
        s3_secret_key=body.s3_secret_key,
        s3_path_prefix=body.s3_path_prefix,
        local_retention_days=body.local_retention_days,
        s3_enabled=body.s3_enabled,
        configured_by_id=current_admin.id,
    )
    await session.commit()
    return BackupConfigOut(
        id=cfg.id,
        s3_endpoint=body.s3_endpoint,
        s3_bucket=cfg.s3_bucket,
        s3_access_key=body.s3_access_key,
        s3_path_prefix=cfg.s3_path_prefix,
        local_retention_days=cfg.local_retention_days,
        s3_enabled=cfg.s3_enabled,
        configured_at=cfg.configured_at,
    )


@router.post("/admin/backup/config/test-s3", response_model=S3TestResult)
async def test_s3(
    current_admin: _Admin,
    session: _DbSession,
) -> S3TestResult:
    success, error = await service.test_s3(session)
    return S3TestResult(success=success, error_detail=error)


@router.delete("/admin/backup/config/s3", status_code=status.HTTP_204_NO_CONTENT)
async def delete_s3(
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    try:
        await service.delete_s3_config(session)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/admin/backup/runs", response_model=BackupRunListOut)
async def list_backup_runs(
    current_admin: _Admin,
    session: _DbSession,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100)] = 20,
) -> BackupRunListOut:
    rows, next_cursor = await service.list_backup_runs(session, limit=limit, cursor=cursor)
    return BackupRunListOut(
        items=[BackupRunOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/admin/backup/trigger",
    response_model=BackupTriggerOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_backup(
    current_admin: _Admin,
    session: _DbSession,
) -> BackupTriggerOut:
    run = await service.trigger_backup(session, triggered_by_id=current_admin.id)
    await session.commit()
    return BackupTriggerOut(backup_run_id=run.id)


# ---------------------------------------------------------------------------
# Registration settings
# ---------------------------------------------------------------------------


@router.get("/admin/registration", response_model=RegistrationSettingsOut)
async def get_registration(
    current_admin: _Admin,
    session: _DbSession,
) -> RegistrationSettingsOut:
    data = await service.get_registration_settings(session)
    return RegistrationSettingsOut(**data)


@router.post("/admin/registration", response_model=RegistrationSettingsOut)
async def update_registration(
    body: RegistrationSettingsIn,
    current_admin: _Admin,
    session: _DbSession,
) -> RegistrationSettingsOut:
    data = await service.update_registration_settings(
        session,
        allow_registration=body.allow_registration,
        registration_limit=body.registration_limit,
        unassigned_account_ttl_days=body.unassigned_account_ttl_days,
        updated_by_id=current_admin.id,
    )
    await session.commit()
    return RegistrationSettingsOut(**data)


# ---------------------------------------------------------------------------
# Emergency read-only toggle
# ---------------------------------------------------------------------------


@router.get("/admin/emergency/read-only", response_model=ReadOnlyStateOut)
async def get_read_only(
    current_admin: _Admin,
    session: _DbSession,
) -> ReadOnlyStateOut:
    row = await service.get_read_only_state(session)
    return ReadOnlyStateOut.model_validate(row)


@router.post("/admin/emergency/read-only", response_model=ReadOnlyStateOut)
async def set_read_only(
    body: SetReadOnlyIn,
    current_admin: _Admin,
    session: _DbSession,
) -> ReadOnlyStateOut:
    row = await service.set_read_only(
        session,
        enabled=body.enabled,
        reason=body.reason,
        enabled_by_id=current_admin.id,
    )
    await session.commit()
    return ReadOnlyStateOut.model_validate(row)


# ---------------------------------------------------------------------------
# Force logout all
# ---------------------------------------------------------------------------


@router.post("/admin/force-logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def force_logout_all(
    body: ForceLogoutAllIn,
    current_admin: _Admin,
    session: _DbSession,
) -> None:
    await service.force_logout_all(session)
    await session.commit()
