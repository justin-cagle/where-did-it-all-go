"""Recurrences domain tables.

Revision ID: a2b3c4d5e6f7
Revises: f1e2d3c4b5a6
Create Date: 2026-05-06 00:00:00.000000

Creates:
  - recurrences_recurrence    -- confirmed recurring payment pattern
  - recurrences_candidate     -- detected candidate awaiting HITL
  - recurrences_exception     -- single-instance override
  - recurrences_match         -- per-transaction match / missed / deviated record

Adds updated_at triggers on all tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "a2b3c4d5e6f7"  # pragma: allowlist secret
down_revision: str | None = "b2c3d4e5f6a7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # recurrences_recurrence
    # ------------------------------------------------------------------
    op.create_table(
        "recurrences_recurrence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("expected_amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "tolerance",
            sa.Numeric(precision=19, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("expected_day_of_period", sa.Integer, nullable=True),
        sa.Column(
            "expected_amount_strategy", sa.String(32), nullable=False, server_default="fixed"
        ),
        sa.Column("linked_category_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("linked_account_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("paused", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("merchant_name", sa.Text, nullable=True),
        sa.Column("recurrence_metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurrences_recurrence_household",
        "recurrences_recurrence",
        ["household_id"],
    )
    op.create_index(
        "ix_recurrences_recurrence_account",
        "recurrences_recurrence",
        ["account_id"],
    )
    op.execute(
        """
        CREATE TRIGGER update_recurrences_recurrence_updated_at
        BEFORE UPDATE ON recurrences_recurrence
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # recurrences_candidate
    # ------------------------------------------------------------------
    op.create_table(
        "recurrences_candidate",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("recurrence_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("merchant_name", sa.Text, nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("expected_amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "sample_transaction_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("occurrence_count", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurrences_candidate_household",
        "recurrences_candidate",
        ["household_id"],
    )
    op.create_index(
        "ix_recurrences_candidate_pending",
        "recurrences_candidate",
        ["household_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.execute(
        """
        CREATE TRIGGER update_recurrences_candidate_updated_at
        BEFORE UPDATE ON recurrences_candidate
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # recurrences_exception
    # ------------------------------------------------------------------
    op.create_table(
        "recurrences_exception",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("recurrence_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("exception_type", sa.String(16), nullable=False),
        sa.Column("affected_period", sa.Date, nullable=False),
        sa.Column("override_amount", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column("override_date", sa.Date, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(
            ["recurrence_id"],
            ["recurrences_recurrence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recurrence_id",
            "affected_period",
            "exception_type",
            name="uq_recurrences_exception_period",
        ),
    )
    op.create_index(
        "ix_recurrences_exception_recurrence",
        "recurrences_exception",
        ["recurrence_id"],
    )
    op.execute(
        """
        CREATE TRIGGER update_recurrences_exception_updated_at
        BEFORE UPDATE ON recurrences_exception
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # recurrences_match
    # ------------------------------------------------------------------
    op.create_table(
        "recurrences_match",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("recurrence_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("transaction_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deviation_amount", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column("deviation_days", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expected_date", sa.Date, nullable=True),
        sa.ForeignKeyConstraint(
            ["recurrence_id"],
            ["recurrences_recurrence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurrences_match_recurrence",
        "recurrences_match",
        ["recurrence_id"],
    )
    op.create_index(
        "ix_recurrences_match_transaction",
        "recurrences_match",
        ["transaction_id"],
        postgresql_where=sa.text("transaction_id IS NOT NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER update_recurrences_match_updated_at
        BEFORE UPDATE ON recurrences_match
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_recurrences_match_updated_at ON recurrences_match")
    op.drop_table("recurrences_match")

    op.execute(
        "DROP TRIGGER IF EXISTS update_recurrences_exception_updated_at ON recurrences_exception"
    )
    op.drop_table("recurrences_exception")

    op.execute(
        "DROP TRIGGER IF EXISTS update_recurrences_candidate_updated_at ON recurrences_candidate"
    )
    op.drop_table("recurrences_candidate")

    op.execute(
        "DROP TRIGGER IF EXISTS update_recurrences_recurrence_updated_at ON recurrences_recurrence"
    )
    op.drop_table("recurrences_recurrence")
