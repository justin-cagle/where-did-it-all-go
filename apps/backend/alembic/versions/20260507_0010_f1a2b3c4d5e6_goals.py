"""Goals domain tables.

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-07 00:00:00.000000

Adds:
  - goals_goal              household financial goals
  - goals_funding_source    per-goal funding sources
  - goals_contribution      contribution event log
  - goals_snapshot          computed burn-up snapshots
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "f1a2b3c4d5e6"  # pragma: allowlist secret
down_revision = "e1f2a3b4c5d6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals_goal",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("goal_type", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "target_amount", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=True
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column(
            "funding_strategy",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'virtual_allocation'"),
        ),
        sa.Column(
            "completion_policy",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'prompt_on_complete'"),
        ),
        sa.Column(
            "auto_extend_amount", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=True
        ),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("linked_debt_plan_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("linked_category_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "minimum_balance_threshold",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["households_user.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_goals_goal_household", "goals_goal", ["household_id"])
    op.create_index("ix_goals_goal_household_status", "goals_goal", ["household_id", "status"])

    op.create_table(
        "goals_funding_source",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("goal_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("attributed_to_user_id", sa.Uuid(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["goal_id"], ["goals_goal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attributed_to_user_id"],
            ["households_user.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_goals_funding_source_goal", "goals_funding_source", ["goal_id"])
    op.create_index("ix_goals_funding_source_household", "goals_funding_source", ["household_id"])

    op.create_table(
        "goals_contribution",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("goal_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("contributed_at", sa.Date, nullable=False),
        sa.Column("contribution_type", sa.String(16), nullable=False),
        sa.Column("transaction_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("attributed_to_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
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
        sa.ForeignKeyConstraint(["goal_id"], ["goals_goal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attributed_to_user_id"],
            ["households_user.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_goals_contribution_goal", "goals_contribution", ["goal_id"])
    op.create_index("ix_goals_contribution_household", "goals_contribution", ["household_id"])
    op.create_index("ix_goals_contribution_transaction", "goals_contribution", ["transaction_id"])
    op.create_unique_constraint(
        "uq_goals_contribution_goal_transaction",
        "goals_contribution",
        ["goal_id", "transaction_id"],
        postgresql_where=sa.text("transaction_id IS NOT NULL"),
    )

    op.create_table(
        "goals_snapshot",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("goal_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column(
            "cumulative_actual", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "cumulative_expected", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False
        ),
        sa.Column(
            "required_pace", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False
        ),
        sa.Column("actual_pace", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("projected_completion_date", sa.Date, nullable=True),
        sa.Column(
            "gap_to_close", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False
        ),
        sa.Column("progress_pct", sa.Numeric(precision=7, scale=4, asdecimal=True), nullable=False),
        sa.Column("burn_up_status", sa.String(16), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
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
        sa.ForeignKeyConstraint(["goal_id"], ["goals_goal.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_goals_snapshot_goal", "goals_snapshot", ["goal_id"])
    op.create_index("ix_goals_snapshot_goal_date", "goals_snapshot", ["goal_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_table("goals_snapshot")
    op.drop_table("goals_contribution")
    op.drop_table("goals_funding_source")
    op.drop_table("goals_goal")
