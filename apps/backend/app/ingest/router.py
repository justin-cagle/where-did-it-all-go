"""FastAPI routes for the ingest module.

All routes scoped under /api/v1/households/{household_id}/ingest/.
Household membership enforced by HouseholdMember dependency.

Routes:
  POST   /sync-configs/                          create SimpleFIN config
  GET    /sync-configs/                          list sync configs
  PATCH  /sync-configs/{config_id}               update label/interval/enabled
  POST   /sync-configs/{config_id}/trigger       enqueue sync_account_job
  GET    /sync-configs/{config_id}/preview       fetch SimpleFIN accounts preview
  POST   /sync-configs/{config_id}/mapping       save account mappings
  DELETE /sync-configs/{config_id}               soft delete
  POST   /csv-mappings                           upsert CSV column mapping
  GET    /csv-mappings/{institution_name}        get saved CSV mapping
  POST   /upload                                 upload OFX or CSV file
  GET    /jobs/                                  list recent import jobs
  GET    /jobs/{import_job_id}                   poll job status + counters
"""

import base64
import json
import urllib.request
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
    CSVMappingIn,
    CSVMappingOut,
    ImportJobOut,
    MappingDecision,
    MappingResult,
    SimplefinAccountPreview,
    SyncConfigCreate,
    SyncConfigOut,
    SyncConfigUpdate,
    TriggerResponse,
    UploadResponse,
)
from app.security.ratelimit import get_household_id, get_limiter
from app.worker.settings import get_redis_settings

router = APIRouter(tags=["ingest"])
limiter = get_limiter()

_DbSession = Annotated[AsyncSession, Depends(get_db)]

_PREVIEW_CACHE_TTL = 300  # 5 minutes in seconds


async def _get_arq_pool() -> arq.ArqRedis:
    redis_settings: RedisSettings = get_redis_settings()
    return await arq.create_pool(redis_settings)


def _exchange_setup_token(setup_token: str) -> str:
    """Exchange a SimpleFIN setup token for an access URL.

    Setup tokens are one-time-use URLs that return the access URL on GET.
    Never log the setup_token or the returned access URL.
    """
    try:
        with urllib.request.urlopen(setup_token, timeout=15) as resp:  # noqa: S310
            access_url = resp.read().decode("utf-8").strip()
    except Exception as exc:
        raise ValueError(f"SimpleFIN token exchange failed: {exc}") from exc
    if not access_url:
        raise ValueError("SimpleFIN returned empty access URL")
    return access_url


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

    credentials: dict[str, object] = {}

    if provider == IngestProvider.SIMPLEFIN:
        if not body.setup_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="setup_token required for simplefin provider",
            )
        try:
            access_url = _exchange_setup_token(body.setup_token)
        except ValueError as exc:
            error_str = str(exc).lower()
            if "already" in error_str or "claimed" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This token has already been used. Generate a new one from SimpleFIN.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not reach SimpleFIN. Check your connection and try again.",
            ) from exc
        credentials = {"access_url": access_url}

    try:
        config = await service.create_sync_config(
            session,
            household_id=household_id,
            provider=provider,
            credentials=credentials,
            master_key=settings.master_key,
            label=body.label,
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


@router.patch(
    "/households/{household_id}/ingest/sync-configs/{config_id}",
    response_model=SyncConfigOut,
)
async def update_sync_config(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    body: SyncConfigUpdate,
    session: _DbSession,
    current_user: CurrentUser,
) -> SyncConfigOut:
    try:
        config = await service.update_sync_config(
            session,
            config_id=config_id,
            household_id=household_id,
            label=body.label,
            sync_interval_hours=body.sync_interval_hours,
            sync_enabled=body.sync_enabled,
        )
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SyncConfigOut.model_validate(config)


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

    if config.status == "rate_limited":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="sync paused — rate limited by SimpleFIN",
        )

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


@router.get(
    "/households/{household_id}/ingest/sync-configs/{config_id}/preview",
    response_model=list[SimplefinAccountPreview],
)
async def preview_simplefin_accounts(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
    request: Request,
) -> list[SimplefinAccountPreview]:
    """Fetch SimpleFIN accounts for a SyncConfig and return preview with suggested types.

    Result is cached in Redis for 5 minutes to avoid repeated SimpleFIN calls.
    Does NOT create any system accounts.
    """
    from app.ingest.service import fetch_simplefin_preview, get_credentials

    try:
        config = await service.get_sync_config(
            session, config_id=config_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if config.provider != "simplefin":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="preview only supported for simplefin provider",
        )

    settings = get_settings()
    cache_key = f"ingest:preview:{config_id}"

    # Try Redis cache
    try:
        import redis.asyncio as aioredis

        redis_url = str(settings.redis_url)
        redis_client = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        cached = await redis_client.get(cache_key)
        if cached is not None:
            await redis_client.aclose()
            cached_data: list[dict[str, object]] = json.loads(cached)
            return [SimplefinAccountPreview.model_validate(a) for a in cached_data]
        await redis_client.aclose()
    except Exception:  # noqa: S110
        pass  # Redis unavailable — proceed without cache

    try:
        creds = get_credentials(config, settings.master_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not decrypt credentials",
        ) from exc

    access_url = str(creds.get("access_url", ""))
    if not access_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SyncConfig has no access_url",
        )

    try:
        accounts = await fetch_simplefin_preview(access_url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Could not fetch accounts from SimpleFIN. "
                f"Check your connection and try again. ({exc})"
            ),
        ) from exc

    # Cache result
    try:
        import redis.asyncio as aioredis

        redis_url = str(settings.redis_url)
        redis_client = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        await redis_client.setex(cache_key, _PREVIEW_CACHE_TTL, json.dumps(accounts))
        await redis_client.aclose()
    except Exception:  # noqa: S110
        pass  # Redis unavailable — skip caching

    return [SimplefinAccountPreview.model_validate(a) for a in accounts]


@router.post(
    "/households/{household_id}/ingest/sync-configs/{config_id}/mapping",
    response_model=MappingResult,
    status_code=status.HTTP_200_OK,
)
async def save_account_mapping(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    body: list[MappingDecision],
    session: _DbSession,
    current_user: CurrentUser,
) -> MappingResult:
    """Save account mapping decisions for a SimpleFIN SyncConfig.

    Creates new accounts, maps existing accounts, or ignores SimpleFIN accounts.
    Sets authoritative_sync_config_id on mapped/created accounts.
    Triggers initial 90-day sync job on first mapping save.
    """
    import sqlalchemy as sa

    from app.accounts.enums import AccountType
    from app.accounts.models import Account

    try:
        await service.get_sync_config(session, config_id=config_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    accounts_created = 0
    accounts_mapped = 0
    accounts_ignored = 0
    is_first_mapping = True

    # Check if any accounts already point to this SyncConfig
    existing_check = await session.execute(
        sa.select(sa.func.count()).where(
            Account.authoritative_sync_config_id == config_id,
            Account.archived_at.is_(None),
        )
    )
    existing_count = existing_check.scalar_one()
    if existing_count > 0:
        is_first_mapping = False

    for decision in body:
        if decision.action == "ignore":
            accounts_ignored += 1
            continue

        elif decision.action == "create":
            new_acct_data = decision.new_account or {}
            acct_type_str = str(new_acct_data.get("type", "checking"))
            try:
                acct_type = AccountType(acct_type_str)
            except ValueError:
                acct_type = AccountType.CHECKING

            import uuid_utils

            new_acct = Account(
                id=uuid_utils.uuid7(),
                household_id=household_id,
                name=str(new_acct_data.get("name", "New Account")),
                account_type=str(acct_type),
                currency=str(new_acct_data.get("currency", "USD")),
                is_manual=False,
                authoritative_sync_config_id=config_id,
                simplefin_account_id=decision.simplefin_account_id,
            )
            session.add(new_acct)
            accounts_created += 1

        elif decision.action == "map":
            if decision.system_account_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="system_account_id required for 'map' action",
                )
            result = await session.execute(
                sa.select(Account).where(
                    Account.id == decision.system_account_id,
                    Account.household_id == household_id,
                    Account.archived_at.is_(None),
                )
            )
            acct = result.scalar_one_or_none()
            if acct is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"account {decision.system_account_id} not found",
                )
            if decision.authoritative:
                acct.authoritative_sync_config_id = config_id
                acct.simplefin_account_id = decision.simplefin_account_id
            accounts_mapped += 1

    await session.flush()
    await session.commit()

    # Trigger initial 90-day sync job on first mapping
    if is_first_mapping and (accounts_created + accounts_mapped) > 0:
        pool = await _get_arq_pool()
        try:
            await pool.enqueue_job(
                "sync_account_job_initial",
                sync_config_id=str(config_id),
            )
        finally:
            await pool.aclose()

    return MappingResult(
        accounts_created=accounts_created,
        accounts_mapped=accounts_mapped,
        accounts_ignored=accounts_ignored,
    )


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
# CSV mapping persistence
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/ingest/csv-mappings",
    response_model=CSVMappingOut,
    status_code=status.HTTP_200_OK,
)
async def upsert_csv_mapping(
    household_id: HouseholdMember,
    body: CSVMappingIn,
    session: _DbSession,
    current_user: CurrentUser,
) -> CSVMappingOut:
    mapping = await service.upsert_csv_mapping(
        session,
        household_id=household_id,
        institution_name=body.institution_name,
        column_map=body.column_map,
        date_format=body.date_format,
        amount_convention=body.amount_convention,
    )
    await session.commit()
    return CSVMappingOut.model_validate(mapping)


@router.get(
    "/households/{household_id}/ingest/csv-mappings/{institution_name}",
    response_model=CSVMappingOut,
)
async def get_csv_mapping(
    household_id: HouseholdMember,
    institution_name: str,
    session: _DbSession,
    current_user: CurrentUser,
) -> CSVMappingOut:
    mapping = await service.get_csv_mapping(
        session, household_id=household_id, institution_name=institution_name
    )
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="csv mapping not found")
    return CSVMappingOut.model_validate(mapping)


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
    filename = file.filename or None
    job_row = await service.create_import_job(
        session, household_id=household_id, source=import_source, filename=filename
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
    "/households/{household_id}/ingest/jobs/",
    response_model=list[ImportJobOut],
)
async def list_import_jobs(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[ImportJobOut]:
    """Return recent import jobs for the household."""
    jobs = await service.list_import_jobs(session, household_id=household_id, limit=limit)
    return [ImportJobOut.model_validate(j) for j in jobs]


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
