"""Service layer for ingest module — SyncConfig and ImportJob CRUD.

No business logic beyond CRUD and state management. Pipeline logic lives in
pipeline.py. Parser logic lives in parsers/.

Credential encryption: SyncConfig.credentials stores {"_enc": "<fernet_token>"}.
Use get_credentials() / set_credentials() to read and write safely.
Never log decrypted credentials or the raw fernet token.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.enums import ImportSource, ImportStatus, IngestProvider
from app.ingest.models import ImportJob, IngestCSVMapping, SyncConfig
from app.security.encryption import DecryptionError, decrypt_dict, encrypt_dict

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a uniqueness or state constraint."""


class ValidationError(Exception):
    """Operation violates a domain invariant."""


# ---------------------------------------------------------------------------
# SyncConfig
# ---------------------------------------------------------------------------


async def create_sync_config(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    provider: IngestProvider,
    credentials: dict[str, Any],
    master_key: str,
    label: str | None = None,
    sync_enabled: bool = True,
) -> SyncConfig:
    """Create a SyncConfig. Credentials are encrypted before storage.

    Raises ConflictError if the household already has a config for this provider+label.
    Never stores plaintext credentials.
    """
    encrypted_token = encrypt_dict(credentials, master_key)
    config = SyncConfig(
        household_id=household_id,
        provider=str(provider),
        credentials={"_enc": encrypted_token},
        label=label,
        sync_enabled=sync_enabled,
    )
    session.add(config)
    await session.flush()
    return config


async def get_sync_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
) -> SyncConfig:
    """Return a SyncConfig. Raises NotFoundError if absent or wrong household."""
    result = await session.execute(
        sa.select(SyncConfig).where(
            SyncConfig.id == config_id,
            SyncConfig.household_id == household_id,
            SyncConfig.archived_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("sync config not found")
    return row


async def list_sync_configs(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
) -> list[SyncConfig]:
    """List all active SyncConfigs for a household."""
    result = await session.execute(
        sa.select(SyncConfig)
        .where(
            SyncConfig.household_id == household_id,
            SyncConfig.archived_at.is_(None),
        )
        .order_by(SyncConfig.created_at)
    )
    return list(result.scalars().all())


async def update_sync_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
    label: str | None = None,
    sync_interval_hours: int | None = None,
    sync_enabled: bool | None = None,
) -> SyncConfig:
    """Update mutable fields on a SyncConfig."""
    config = await get_sync_config(session, config_id=config_id, household_id=household_id)
    if label is not None:
        config.label = label
    if sync_interval_hours is not None:
        config.sync_interval_hours = sync_interval_hours
    if sync_enabled is not None:
        config.sync_enabled = sync_enabled
        if not sync_enabled:
            config.status = "disabled"
        elif config.status == "disabled":
            config.status = "active"
    await session.flush()
    return config


async def archive_sync_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a SyncConfig."""
    row = await get_sync_config(session, config_id=config_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    row.archived_at = now
    row.archived_by = actor_id
    await session.flush()


def get_credentials(config: SyncConfig, master_key: str) -> dict[str, Any]:
    """Decrypt and return the credentials dict from a SyncConfig.

    Raises DecryptionError if the master_key is wrong or data is corrupted.
    Never log the return value.
    """
    token = config.credentials.get("_enc", "")
    if not token:
        raise DecryptionError("credentials field is empty or not encrypted")
    return decrypt_dict(str(token), master_key)


async def mark_last_synced(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
) -> None:
    """Update last_synced_at to now on a SyncConfig."""
    await session.execute(
        sa.update(SyncConfig)
        .where(SyncConfig.id == config_id)
        .values(last_synced_at=datetime.now(tz=UTC))
    )


async def update_sync_status(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    status: str,
    last_error: str | None = None,
    next_sync_at: datetime | None = None,
) -> None:
    """Update status fields on a SyncConfig after a sync attempt."""
    values: dict[str, Any] = {"status": status}
    if last_error is not None:
        values["last_error"] = last_error
    if next_sync_at is not None:
        values["next_sync_at"] = next_sync_at
    await session.execute(sa.update(SyncConfig).where(SyncConfig.id == config_id).values(**values))


async def increment_requests_today(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
) -> int:
    """Increment requests_today, resetting if the date has changed. Returns new count."""
    today = date.today()
    result = await session.execute(
        sa.select(SyncConfig.requests_today, SyncConfig.requests_today_reset_at).where(
            SyncConfig.id == config_id
        )
    )
    row = result.one_or_none()
    if row is None:
        return 0
    current_count, reset_at = row
    if reset_at is None or reset_at < today:
        new_count = 1
    else:
        new_count = (current_count or 0) + 1
    await session.execute(
        sa.update(SyncConfig)
        .where(SyncConfig.id == config_id)
        .values(requests_today=new_count, requests_today_reset_at=today)
    )
    return new_count


# ---------------------------------------------------------------------------
# Preview — fetch SimpleFIN accounts without creating system accounts
# ---------------------------------------------------------------------------


def _infer_account_type(org_name: str, account_name: str) -> str:
    """Heuristic: guess account type from institution/account name."""
    name_lower = (account_name + " " + org_name).lower()
    if any(w in name_lower for w in ("credit", "visa", "mastercard", "amex", "discover")):
        return "credit_card"
    if any(w in name_lower for w in ("loan", "mortgage", "auto")):
        return "loan"
    if any(w in name_lower for w in ("saving", "hysa", "sav")):
        return "savings"
    if any(w in name_lower for w in ("invest", "brokerage", "ira", "401k", "roth")):
        return "investment"
    return "checking"


async def fetch_simplefin_preview(
    access_url: str,
) -> list[dict[str, Any]]:
    """Call SimpleFIN /accounts and return preview data without date filtering.

    Returns list of dicts matching SimplefinAccountPreview schema.
    Never creates system accounts.
    """
    import httpx

    url = f"{access_url}/accounts"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for account in data.get("accounts", []):
        org = account.get("org", {})
        institution_name = org.get("name", "Unknown Institution")
        acct_id = account.get("id", "")
        acct_name = account.get("name", "")
        acct_number = account.get("account-id", "") or ""
        last4 = acct_number[-4:] if len(acct_number) >= 4 else acct_number or None

        raw_balance = str(account.get("balance", "0"))
        try:
            balance_dec = Decimal(raw_balance)
        except InvalidOperation:
            balance_dec = Decimal("0")

        currency = str(account.get("currency", "USD")).upper()
        suggested_type = _infer_account_type(institution_name, acct_name)

        results.append(
            {
                "simplefin_account_id": acct_id,
                "institution_name": institution_name,
                "account_name": acct_name,
                "account_number_last4": last4,
                "balance": str(balance_dec),
                "currency": currency,
                "suggested_type": suggested_type,
            }
        )
    return results


# ---------------------------------------------------------------------------
# CSV mapping persistence
# ---------------------------------------------------------------------------


async def upsert_csv_mapping(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    institution_name: str,
    column_map: dict[str, Any],
    date_format: str | None,
    amount_convention: str,
) -> IngestCSVMapping:
    """Upsert a CSV column mapping for an institution."""
    result = await session.execute(
        sa.select(IngestCSVMapping).where(
            IngestCSVMapping.household_id == household_id,
            IngestCSVMapping.institution_name == institution_name,
            IngestCSVMapping.archived_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.column_map = column_map
        existing.date_format = date_format
        existing.amount_convention = amount_convention
        await session.flush()
        return existing

    mapping = IngestCSVMapping(
        household_id=household_id,
        institution_name=institution_name,
        column_map=column_map,
        date_format=date_format,
        amount_convention=amount_convention,
    )
    session.add(mapping)
    await session.flush()
    return mapping


async def get_csv_mapping(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    institution_name: str,
) -> IngestCSVMapping | None:
    """Return a saved CSV mapping, or None if not found."""
    result = await session.execute(
        sa.select(IngestCSVMapping).where(
            IngestCSVMapping.household_id == household_id,
            IngestCSVMapping.institution_name == institution_name,
            IngestCSVMapping.archived_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# ImportJob
# ---------------------------------------------------------------------------


async def create_import_job(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: ImportSource,
    filename: str | None = None,
) -> ImportJob:
    """Create an ImportJob in pending state."""
    job = ImportJob(
        household_id=household_id,
        source=str(source),
        status=str(ImportStatus.PENDING),
        filename=filename,
    )
    session.add(job)
    await session.flush()
    return job


async def mark_job_running(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
) -> None:
    """Transition ImportJob to running state."""
    await session.execute(
        sa.update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(status=str(ImportStatus.RUNNING), started_at=datetime.now(tz=UTC))
    )


async def mark_job_failed(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    error: str,
) -> None:
    """Transition ImportJob to failed state with error detail."""
    await session.execute(
        sa.update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(
            status=str(ImportStatus.FAILED),
            completed_at=datetime.now(tz=UTC),
            error_detail={"error": error},
        )
    )


async def mark_job_complete(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    imported: int = 0,
    duplicate: int = 0,
    errors: int = 0,
) -> None:
    """Transition ImportJob to completed state with aggregate counts."""
    await session.execute(
        sa.update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(
            status=str(ImportStatus.COMPLETED),
            completed_at=datetime.now(tz=UTC),
            imported_count=imported,
            duplicate_count=duplicate,
            error_count=errors,
        )
    )


async def get_import_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    household_id: uuid.UUID,
) -> ImportJob:
    """Return an ImportJob. Raises NotFoundError if absent or wrong household."""
    result = await session.execute(
        sa.select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.household_id == household_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("import job not found")
    return row


async def list_import_jobs(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    limit: int = 10,
) -> list[ImportJob]:
    """Return recent ImportJobs for the household, newest first."""
    result = await session.execute(
        sa.select(ImportJob)
        .where(
            ImportJob.household_id == household_id,
            ImportJob.archived_at.is_(None),
        )
        .order_by(ImportJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
