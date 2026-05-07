"""Recommendations domain tables.

Revision ID: c1d2e3f4a5b6
Revises: a2b3c4d5e6f7
Create Date: 2026-05-06 00:00:00.000000

Creates:
  - recommendations_recommendation   -- cross-module intent and resolution tracker
  - recommendations_auto_apply_rule  -- per-source auto-apply preference per household

Drops:
  - recommendations_pending          -- stub table from ingest migration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "c1d2e3f4a5b6"  # pragma: allowlist secret
down_revision: str | None = "a2b3c4d5e6f7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Drop stub table from ingest migration
    # ------------------------------------------------------------------
    op.drop_index("ix_recommendations_pending_household", table_name="recommendations_pending")
    op.drop_table("recommendations_pending")

    # ------------------------------------------------------------------
    # recommendations_recommendation
    # ------------------------------------------------------------------
    op.create_table(
        "recommendations_recommendation",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("target_subsystem", sa.Text, nullable=False),
        sa.Column("target_entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "proposed_value",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("rationale_text", sa.Text, nullable=False),
        sa.Column(
            "rationale_data",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("auto_apply", sa.Boolean, nullable=False, server_default="false"),
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
    op.create_index(
        "ix_recommendations_recommendation_household",
        "recommendations_recommendation",
        ["household_id"],
    )
    op.create_index(
        "ix_recommendations_recommendation_pending",
        "recommendations_recommendation",
        ["household_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_recommendations_recommendation_source",
        "recommendations_recommendation",
        ["source"],
    )

    # ------------------------------------------------------------------
    # recommendations_auto_apply_rule
    # ------------------------------------------------------------------
    op.create_table(
        "recommendations_auto_apply_rule",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="false"),
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
        sa.UniqueConstraint(
            "household_id",
            "source",
            name="uq_recommendations_auto_apply_rule_household_source",
        ),
    )
    op.create_index(
        "ix_recommendations_auto_apply_rule_household",
        "recommendations_auto_apply_rule",
        ["household_id"],
    )

    # updated_at trigger (reuse the shared helper if available)
    for table in (
        "recommendations_recommendation",
        "recommendations_auto_apply_rule",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """
        )


def downgrade() -> None:
    for table in (
        "recommendations_auto_apply_rule",
        "recommendations_recommendation",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.drop_index(
        "ix_recommendations_auto_apply_rule_household",
        table_name="recommendations_auto_apply_rule",
    )
    op.drop_table("recommendations_auto_apply_rule")

    op.drop_index(
        "ix_recommendations_recommendation_source",
        table_name="recommendations_recommendation",
    )
    op.drop_index(
        "ix_recommendations_recommendation_pending",
        table_name="recommendations_recommendation",
    )
    op.drop_index(
        "ix_recommendations_recommendation_household",
        table_name="recommendations_recommendation",
    )
    op.drop_table("recommendations_recommendation")

    # Re-create the stub table so this migration is reversible
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
