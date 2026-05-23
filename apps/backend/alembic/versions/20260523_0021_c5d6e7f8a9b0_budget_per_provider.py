"""Add provider_config_id FK to token budget (per-provider budget scoping).

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c5d6e7f8a9b0"  # pragma: allowlist secret
down_revision = "b4c5d6e7f8a9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_insights_token_budget_household_period",
        "insights_token_budget",
        type_="unique",
    )
    op.add_column(
        "insights_token_budget",
        sa.Column("provider_config_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_insights_token_budget_provider_config",
        "insights_token_budget",
        "insights_provider_config",
        ["provider_config_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_insights_token_budget_provider_config",
        "insights_token_budget",
        ["provider_config_id"],
    )
    op.execute(
        sa.text(
            "ALTER TABLE insights_token_budget "
            "ADD CONSTRAINT uq_insights_token_budget_household_period_provider "
            "UNIQUE NULLS NOT DISTINCT (household_id, period_start, provider_config_id)"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_insights_token_budget_household_period_provider",
        "insights_token_budget",
        type_="unique",
    )
    op.drop_index(
        "ix_insights_token_budget_provider_config",
        table_name="insights_token_budget",
    )
    op.drop_constraint(
        "fk_insights_token_budget_provider_config",
        "insights_token_budget",
        type_="foreignkey",
    )
    op.drop_column("insights_token_budget", "provider_config_id")
    op.create_unique_constraint(
        "uq_insights_token_budget_household_period",
        "insights_token_budget",
        ["household_id", "period_start"],
    )
