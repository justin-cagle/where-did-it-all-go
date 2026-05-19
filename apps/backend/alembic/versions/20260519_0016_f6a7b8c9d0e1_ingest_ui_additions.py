"""ingest ui additions: sync config fields, csv mapping, account/tx cross-refs

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-19

Changes:
- ingest_sync_config: make account_id nullable, drop FK + old unique constraint;
  add label, sync_interval_hours, requests_today, requests_today_reset_at,
  next_sync_at, last_error, status
- ingest_import_job: add filename
- accounts_account: add authoritative_sync_config_id, simplefin_account_id
- transactions_transaction: add import_job_id + index
- ingest_csv_mapping: new table
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# pragma: allowlist secret
revision: str = "f6a7b8c9d0e1"  # pragma: allowlist secret
down_revision: str | None = "e5f6a7b8c9d0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # ingest_sync_config — drop old FK/constraint, add new fields
    # ---------------------------------------------------------------------------
    op.drop_constraint(
        "uq_ingest_sync_config_account_provider",
        "ingest_sync_config",
        type_="unique",
    )
    op.drop_index("ix_ingest_sync_config_account", table_name="ingest_sync_config")
    op.drop_constraint(
        "ingest_sync_config_account_id_fkey",
        "ingest_sync_config",
        type_="foreignkey",
    )
    op.execute(sa.text("ALTER TABLE ingest_sync_config ALTER COLUMN account_id DROP NOT NULL"))
    op.add_column(
        "ingest_sync_config",
        sa.Column("label", sa.Text(), nullable=True),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column(
            "sync_interval_hours",
            sa.Integer(),
            nullable=False,
            server_default="4",
        ),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column(
            "requests_today",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column("requests_today_reset_at", sa.Date(), nullable=True),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "ingest_sync_config",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
    )

    # ---------------------------------------------------------------------------
    # ingest_import_job — add filename
    # ---------------------------------------------------------------------------
    op.add_column(
        "ingest_import_job",
        sa.Column("filename", sa.Text(), nullable=True),
    )

    # ---------------------------------------------------------------------------
    # accounts_account — add cross-module refs
    # ---------------------------------------------------------------------------
    op.add_column(
        "accounts_account",
        sa.Column(
            "authoritative_sync_config_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "accounts_account",
        sa.Column("simplefin_account_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_accounts_account_authoritative_sync",
        "accounts_account",
        ["authoritative_sync_config_id"],
    )

    # ---------------------------------------------------------------------------
    # transactions_transaction — add import_job_id
    # ---------------------------------------------------------------------------
    op.add_column(
        "transactions_transaction",
        sa.Column(
            "import_job_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_transactions_transaction_import_job",
        "transactions_transaction",
        ["import_job_id"],
    )

    # ---------------------------------------------------------------------------
    # ingest_csv_mapping — new table
    # ---------------------------------------------------------------------------
    op.create_table(
        "ingest_csv_mapping",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("institution_name", sa.Text(), nullable=False),
        sa.Column(
            "column_map",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("date_format", sa.Text(), nullable=True),
        sa.Column(
            "amount_convention",
            sa.String(32),
            nullable=False,
            server_default="positive_is_credit",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "institution_name",
            name="uq_ingest_csv_mapping_household_institution",
        ),
    )
    op.create_index(
        "ix_ingest_csv_mapping_household",
        "ingest_csv_mapping",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_csv_mapping_household", table_name="ingest_csv_mapping")
    op.drop_table("ingest_csv_mapping")

    op.drop_index(
        "ix_transactions_transaction_import_job",
        table_name="transactions_transaction",
    )
    op.execute(sa.text("ALTER TABLE transactions_transaction DROP COLUMN IF EXISTS import_job_id"))

    op.drop_index(
        "ix_accounts_account_authoritative_sync",
        table_name="accounts_account",
    )
    op.execute(
        sa.text("ALTER TABLE accounts_account DROP COLUMN IF EXISTS authoritative_sync_config_id")
    )
    op.execute(sa.text("ALTER TABLE accounts_account DROP COLUMN IF EXISTS simplefin_account_id"))

    op.execute(sa.text("ALTER TABLE ingest_import_job DROP COLUMN IF EXISTS filename"))

    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS status"))
    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS last_error"))
    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS next_sync_at"))
    op.execute(
        sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS requests_today_reset_at")
    )
    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS requests_today"))
    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS sync_interval_hours"))
    op.execute(sa.text("ALTER TABLE ingest_sync_config DROP COLUMN IF EXISTS label"))

    # Restore account_id NOT NULL + FK + index + unique that upgrade() dropped
    op.execute(sa.text("ALTER TABLE ingest_sync_config ALTER COLUMN account_id SET NOT NULL"))
    op.create_index("ix_ingest_sync_config_account", "ingest_sync_config", ["account_id"])
    op.create_foreign_key(
        "ingest_sync_config_account_id_fkey",
        "ingest_sync_config",
        "accounts_account",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_ingest_sync_config_account_provider",
        "ingest_sync_config",
        ["account_id", "provider"],
    )
