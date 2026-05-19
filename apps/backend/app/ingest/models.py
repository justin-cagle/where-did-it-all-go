"""SQLAlchemy models for the ingest module.

Tables:
  ingest_sync_config    -- per-credential sync configuration and encrypted credentials
  ingest_import_job     -- tracks one import run (upload or scheduled sync)
  ingest_csv_mapping    -- saved CSV column mapping per institution
"""

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SyncConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Provider configuration for a SimpleFIN credential (one per Access Token).

    credentials JSONB stores {"_enc": "<fernet_token>"} — never plaintext.
    Decrypt via security.encryption.decrypt_dict before use.
    Never log the credentials field or its decrypted contents.

    One SyncConfig covers all bank accounts reachable via one Access Token.
    Accounts are linked via Account.authoritative_sync_config_id (no FK — cross-module).
    """

    __tablename__ = "ingest_sync_config"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
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
        server_default=sa.text("'{}'::jsonb"),
        comment='encrypted as {"_enc": "<fernet_token>"} — never stored plaintext',
    )
    label: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="User-assigned credential display name",
    )
    sync_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    sync_interval_hours: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=4,
        server_default="4",
        comment="Sync interval: 1 | 2 | 4 | 8 | 24 hours",
    )
    requests_today: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="SimpleFIN requests made today; reset daily by ARQ cron",
    )
    requests_today_reset_at: Mapped[date | None] = mapped_column(
        sa.Date,
        nullable=True,
        comment="Date when requests_today counter was last reset",
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="When next scheduled sync should run; null = schedule normally",
    )
    last_error: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Last sync error message",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="active",
        server_default="active",
        comment="active | warning | rate_limited | error | disabled",
    )

    __table_args__ = (sa.Index("ix_ingest_sync_config_household", "household_id"),)

    def __repr__(self) -> str:
        return f"SyncConfig(id={self.id}, provider={self.provider!r}, label={self.label!r})"


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
    filename: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Original filename for file uploads",
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


class IngestCSVMapping(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Saved CSV column mapping per institution for a household.

    Upserted on institution_name — one saved mapping per institution per household.
    """

    __tablename__ = "ingest_csv_mapping"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    institution_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    column_map: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Maps column index or header name to field role (date/amount/description/etc)",
    )
    date_format: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    amount_convention: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="positive_is_credit",
        server_default="positive_is_credit",
        comment="positive_is_credit | positive_is_debit",
    )

    __table_args__ = (
        sa.Index("ix_ingest_csv_mapping_household", "household_id"),
        sa.UniqueConstraint(
            "household_id",
            "institution_name",
            name="uq_ingest_csv_mapping_household_institution",
        ),
    )

    def __repr__(self) -> str:
        return f"IngestCSVMapping(id={self.id}, institution={self.institution_name!r})"
