"""Debts domain tables.

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-05-07 00:00:00.000000

Adds:
  - debts_debt_plan             versioned payoff strategy plan
  - debts_debt_plan_schedule    per-account per-month amortization cache
  - debts_debt_plan_summary     aggregate payoff stats cache
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "e1f2a3b4c5d6"  # pragma: allowlist secret
down_revision = "d1e2f3a4b5c6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debts_debt_plan",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("plan_group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column(
            "monthly_extra_payment",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("snowball_flow", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "account_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
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
    )
    op.create_index("ix_debts_debt_plan_household", "debts_debt_plan", ["household_id"])
    op.create_index("ix_debts_debt_plan_group", "debts_debt_plan", ["plan_group_id"])
    op.create_index(
        "ix_debts_debt_plan_group_current",
        "debts_debt_plan",
        ["plan_group_id"],
        postgresql_where=sa.text("effective_to IS NULL AND archived_at IS NULL"),
    )

    op.create_table(
        "debts_debt_plan_schedule",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("debts_debt_plan.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_date", sa.Date, nullable=False),
        sa.Column(
            "opening_balance",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("payment", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("principal", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("interest", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column(
            "closing_balance",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
        ),
        sa.Column("is_payoff", sa.Boolean, nullable=False, server_default=sa.text("false")),
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
        sa.UniqueConstraint(
            "plan_id",
            "account_id",
            "period_date",
            name="uq_debts_schedule_plan_account_period",
        ),
    )
    op.create_index("ix_debts_schedule_plan", "debts_debt_plan_schedule", ["plan_id"])
    op.create_index("ix_debts_schedule_household", "debts_debt_plan_schedule", ["household_id"])
    op.create_index("ix_debts_schedule_account", "debts_debt_plan_schedule", ["account_id"])

    op.create_table(
        "debts_debt_plan_summary",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("debts_debt_plan.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "total_interest",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("total_paid", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("months_to_payoff", sa.Integer, nullable=False),
        sa.Column(
            "interest_savings_vs_minimums",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("payoff_date", sa.Date, nullable=True),
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
    )
    op.create_index("ix_debts_summary_plan", "debts_debt_plan_summary", ["plan_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_debts_summary_plan", table_name="debts_debt_plan_summary")
    op.drop_table("debts_debt_plan_summary")

    op.drop_index("ix_debts_schedule_account", table_name="debts_debt_plan_schedule")
    op.drop_index("ix_debts_schedule_household", table_name="debts_debt_plan_schedule")
    op.drop_index("ix_debts_schedule_plan", table_name="debts_debt_plan_schedule")
    op.drop_table("debts_debt_plan_schedule")

    op.drop_index("ix_debts_debt_plan_group_current", table_name="debts_debt_plan")
    op.drop_index("ix_debts_debt_plan_group", table_name="debts_debt_plan")
    op.drop_index("ix_debts_debt_plan_household", table_name="debts_debt_plan")
    op.drop_table("debts_debt_plan")
