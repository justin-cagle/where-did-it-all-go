"""Insights domain tables.

Revision ID: b1c2d3e4f5a6
Revises: a4b5c6d7e8f9
Create Date: 2026-05-14 00:00:00.000000

Adds:
  - insights_provider_config    per-household AI provider configuration
  - insights_token_budget       per-period token and cost limits + usage
  - insights_audit_log          append-only record of every LLM call
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b1c2d3e4f5a6"  # pragma: allowlist secret
down_revision = "a4b5c6d7e8f9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights_provider_config",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("model_name", sa.Text, nullable=True),
        sa.Column("credentials_encrypted", sa.Text, nullable=True),
        sa.Column(
            "ai_data_sharing",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'generalizations_only'"),
        ),
        # TimestampMixin
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
        # SoftDeleteMixin
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_insights_provider_config_household",
        "insights_provider_config",
        ["household_id"],
    )
    op.create_index(
        "ix_insights_provider_config_household_priority",
        "insights_provider_config",
        ["household_id", "priority"],
    )

    op.create_table(
        "insights_token_budget",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("token_limit", sa.Integer, nullable=True),
        sa.Column(
            "cost_limit",
            sa.Numeric(precision=10, scale=4, asdecimal=True),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column(
            "tokens_used",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_used",
            sa.Numeric(precision=10, scale=4, asdecimal=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "overage_behavior",
            sa.String(24),
            nullable=False,
            server_default=sa.text("'block'"),
        ),
        # TimestampMixin
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
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "household_id",
            "period_start",
            name="uq_insights_token_budget_household_period",
        ),
    )
    op.create_index(
        "ix_insights_token_budget_household",
        "insights_token_budget",
        ["household_id"],
    )

    op.create_table(
        "insights_audit_log",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("prompt_fingerprint", sa.Text, nullable=False),
        sa.Column("response_fingerprint", sa.Text, nullable=True),
        sa.Column(
            "tokens_used",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost",
            sa.Numeric(precision=10, scale=4, asdecimal=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column("insight_category", sa.String(32), nullable=False),
        sa.Column(
            "duration_ms",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_insights_audit_log_household",
        "insights_audit_log",
        ["household_id"],
    )
    op.create_index(
        "ix_insights_audit_log_household_created",
        "insights_audit_log",
        ["household_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("insights_audit_log")
    op.drop_table("insights_token_budget")
    op.drop_table("insights_provider_config")
