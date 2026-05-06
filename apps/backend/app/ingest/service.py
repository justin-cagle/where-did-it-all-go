"""Service layer for ingest module — SyncConfig and ImportJob CRUD.

No business logic beyond CRUD and state management. Pipeline logic lives in
pipeline.py. Parser logic lives in parsers/.

Credential encryption: SyncConfig.credentials stores {"_enc": "<fernet_token>"}.
Use get_credentials() / set_credentials() to read and write safely.
Never log decrypted credentials or the raw fernet token.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.enums import ImportSource, ImportStatus, IngestProvider
from app.ingest.models import ImportJob, SyncConfig
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
    account_id: uuid.UUID,
    provider: IngestProvider,
    credentials: dict[str, Any],
    master_key: str,
    sync_enabled: bool = True,
) -> SyncConfig:
    """Create a SyncConfig. Credentials are encrypted before storage.

    Raises ConflictError if the account already has a config for this provider.
    Never stores plaintext credentials.
    """
    existing = await session.execute(
        sa.select(SyncConfig).where(
            SyncConfig.account_id == account_id,
            SyncConfig.provider == str(provider),
            SyncConfig.archived_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"account {account_id} already has a {provider} sync config")

    encrypted_token = encrypt_dict(credentials, master_key)
    config = SyncConfig(
        household_id=household_id,
        account_id=account_id,
        provider=str(provider),
        credentials={"_enc": encrypted_token},
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
        .where(SyncConfig.household_id == household_id)
        .order_by(SyncConfig.created_at)
    )
    return list(result.scalars().all())


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


# ---------------------------------------------------------------------------
# ImportJob
# ---------------------------------------------------------------------------


async def create_import_job(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    source: ImportSource,
) -> ImportJob:
    """Create an ImportJob in pending state."""
    job = ImportJob(
        household_id=household_id,
        source=str(source),
        status=str(ImportStatus.PENDING),
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
