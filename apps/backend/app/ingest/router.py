"""FastAPI routes for the ingest module.

All routes scoped under /api/v1/households/{household_id}/ingest/.
Household membership enforced by HouseholdMember dependency.

Routes:
  POST   /sync-configs/                          create SimpleFIN or CSV config
  GET    /sync-configs/                          list sync configs
  POST   /sync-configs/{config_id}/trigger       enqueue sync_account_job
  DELETE /sync-configs/{config_id}               soft delete
  POST   /upload                                 upload OFX or CSV file
  GET    /jobs/{import_job_id}                   poll job status + counters
"""

import base64
import uuid
from typing import Annotated

import arq
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.households.deps import CurrentUser
from app.ingest import service
from app.ingest.deps import HouseholdMember
from app.ingest.enums import ImportSource, IngestProvider
from app.ingest.schemas import (
    ImportJobOut,
    SyncConfigCreate,
    SyncConfigOut,
    TriggerResponse,
    UploadResponse,
)
from app.security.ratelimit import get_household_id, get_limiter
from app.worker.settings import get_redis_settings

router = APIRouter(tags=["ingest"])
limiter = get_limiter()

_DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_arq_pool() -> arq.ArqRedis:
    """Yield an ARQ connection pool."""
    redis_settings: RedisSettings = get_redis_settings()
    return await arq.create_pool(redis_settings)


# ---------------------------------------------------------------------------
# Sync configs
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/ingest/sync-configs/",
    response_model=SyncConfigOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_sync_config(
    household_id: HouseholdMember,
    body: SyncConfigCreate,
    session: _DbSession,
    current_user: CurrentUser,
) -> SyncConfigOut:
    settings = get_settings()
    try:
        provider = IngestProvider(body.provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown provider: {body.provider!r}",
        ) from None

    try:
        config = await service.create_sync_config(
            session,
            household_id=household_id,
            account_id=body.account_id,
            provider=provider,
            credentials=body.credentials,
            master_key=settings.master_key,
            sync_enabled=body.sync_enabled,
        )
        await session.commit()
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return SyncConfigOut.model_validate(config)


@router.get(
    "/households/{household_id}/ingest/sync-configs/",
    response_model=list[SyncConfigOut],
)
async def list_sync_configs(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
) -> list[SyncConfigOut]:
    configs = await service.list_sync_configs(session, household_id=household_id)
    return [SyncConfigOut.model_validate(c) for c in configs]


@router.post(
    "/households/{household_id}/ingest/sync-configs/{config_id}/trigger",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_sync(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
) -> TriggerResponse:
    """Enqueue sync_account_job for a SimpleFIN sync config. Returns job ID."""
    try:
        config = await service.get_sync_config(
            session, config_id=config_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if config.provider != "simplefin":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="trigger only supports simplefin provider; use /upload for file-based sources",
        )

    # Create ImportJob record immediately so caller can poll it
    job_row = await service.create_import_job(
        session, household_id=household_id, source=ImportSource.SIMPLEFIN
    )
    await session.commit()

    pool = await _get_arq_pool()
    try:
        await pool.enqueue_job(
            "sync_account_job",
            sync_config_id=str(config.id),
        )
    finally:
        await pool.aclose()

    return TriggerResponse(import_job_id=job_row.id)


@router.delete(
    "/households/{household_id}/ingest/sync-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sync_config(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
) -> None:
    try:
        await service.archive_sync_config(
            session,
            config_id=config_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/ingest/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/minute", key_func=get_household_id)  # type: ignore[misc]
async def upload_file(
    request: Request,
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(...)],
    account_id: Annotated[uuid.UUID, Query(...)],
    source: Annotated[str, Query(pattern="^(ofx_upload|csv_upload|statement)$")] = "ofx_upload",
    csv_config: Annotated[str | None, Query()] = None,
) -> UploadResponse:
    """Accept a multipart OFX/QFX or CSV upload, enqueue processing job.

    File bytes are read in-memory, base64-encoded, and sent to the ARQ job.
    The bytes are NOT stored in the database.
    csv_config: JSON-encoded column mapping config (required for csv_upload).
    """
    import json

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="empty file",
        )

    parsed_csv_config: dict[str, object] | None = None
    if source == "csv_upload":
        if not csv_config:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="csv_config query parameter required for csv_upload",
            )
        try:
            parsed_csv_config = json.loads(csv_config)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"csv_config is not valid JSON: {exc}",
            ) from exc

    import_source = ImportSource(source)
    job_row = await service.create_import_job(
        session, household_id=household_id, source=import_source
    )
    await session.commit()

    pool = await _get_arq_pool()
    try:
        await pool.enqueue_job(
            "process_upload_job",
            import_job_id=str(job_row.id),
            file_bytes_b64=base64.b64encode(content).decode(),
            source=source,
            account_id=str(account_id),
            household_id=str(household_id),
            csv_config=parsed_csv_config,
        )
    finally:
        await pool.aclose()

    return UploadResponse(import_job_id=job_row.id)


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/ingest/jobs/{import_job_id}",
    response_model=ImportJobOut,
)
async def get_import_job(
    household_id: HouseholdMember,
    import_job_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
) -> ImportJobOut:
    try:
        job = await service.get_import_job(session, job_id=import_job_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ImportJobOut.model_validate(job)
