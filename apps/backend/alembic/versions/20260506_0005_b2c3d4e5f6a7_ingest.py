"""Ingest domain tables.

Revision ID: b2c3d4e5f6a7
Revises: f1e2d3c4b5a6
Create Date: 2026-05-06 00:00:00.000000

Creates:
  - ingest_sync_config          -- provider config per account (encrypted credentials)
  - ingest_import_job           -- tracks one import run (upload or scheduled sync)
  - recommendations_pending     -- stub table for cross-module suggestion queue
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "b2c3d4e5f6a7"  # pragma: allowlist secret
down_revision: str | None = "f1e2d3c4b5a6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ingest_sync_config
    # ------------------------------------------------------------------
    op.create_table(
        "ingest_sync_config",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("accounts_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column(
            "credentials",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="encrypted as {_enc: <fernet_token>} — never stored plaintext",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "provider", name="uq_ingest_sync_config_account_provider"
        ),
    )
    op.create_index("ix_ingest_sync_config_household", "ingest_sync_config", ["household_id"])
    op.create_index("ix_ingest_sync_config_account", "ingest_sync_config", ["account_id"])

    # ------------------------------------------------------------------
    # ingest_import_job
    # ------------------------------------------------------------------
    op.create_table(
        "ingest_import_job",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_detail", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_import_job_household", "ingest_import_job", ["household_id"])
    op.create_index("ix_ingest_import_job_status", "ingest_import_job", ["status"])

    # ------------------------------------------------------------------
    # recommendations_pending  (stub — full module replaces this later)
    # ------------------------------------------------------------------
    op.create_table(
        "recommendations_pending",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendations_pending_household", "recommendations_pending", ["household_id"]
    )


def downgrade() -> None:
    op.drop_table("recommendations_pending")
    op.drop_index("ix_ingest_import_job_status", table_name="ingest_import_job")
    op.drop_index("ix_ingest_import_job_household", table_name="ingest_import_job")
    op.drop_table("ingest_import_job")
    op.drop_index("ix_ingest_sync_config_account", table_name="ingest_sync_config")
    op.drop_index("ix_ingest_sync_config_household", table_name="ingest_sync_config")
    op.drop_table("ingest_sync_config")
