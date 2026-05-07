"""SQLAlchemy models for the ingest module.

Tables:
  ingest_sync_config  -- per-account sync configuration and encrypted credentials
  ingest_import_job   -- tracks one import run (upload or scheduled sync)
"""

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SyncConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Provider configuration for an account's automated sync.

    credentials JSONB stores {"_enc": "<fernet_token>"} — never plaintext.
    Decrypt via security.encryption.decrypt_dict before use.
    Never log the credentials field or its decrypted contents.
    """

    __tablename__ = "ingest_sync_config"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="simplefin | ofx | csv | manual",
    )
    credentials: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment='encrypted as {"_enc": "<fernet_token>"} — never stored plaintext',
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    sync_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
    )

    __table_args__ = (
        sa.Index("ix_ingest_sync_config_household", "household_id"),
        sa.Index("ix_ingest_sync_config_account", "account_id"),
        sa.UniqueConstraint(
            "account_id", "provider", name="uq_ingest_sync_config_account_provider"
        ),
    )

    def __repr__(self) -> str:
        return f"SyncConfig(id={self.id}, provider={self.provider!r}, account_id={self.account_id})"


class ImportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Record of a single import run (upload or sync)."""

    __tablename__ = "ingest_import_job"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="simplefin | ofx_upload | csv_upload | statement",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        comment="pending | running | completed | failed",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    row_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        sa.Index("ix_ingest_import_job_household", "household_id"),
        sa.Index("ix_ingest_import_job_status", "status"),
    )

    def __repr__(self) -> str:
        return f"ImportJob(id={self.id}, source={self.source!r}, status={self.status!r})"
