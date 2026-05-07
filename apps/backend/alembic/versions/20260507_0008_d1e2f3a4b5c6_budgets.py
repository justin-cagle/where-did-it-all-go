"""Budgets domain tables + budget_role column on classification_category.

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-05-07 00:00:00.000000

Adds:
  - classification_category.budget_role  (additive column, default uncategorized)
  - budgets_budget                        versioned budget plan
  - budgets_budget_line                   per-category allocation
  - budgets_period_actual                 computed actuals cache
  - budgets_period_income                 manual per-period income overrides
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "d1e2f3a4b5c6"  # pragma: allowlist secret
down_revision: str | None = "c1d2e3f4a5b6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Additive column on classification_category (no data loss)
    # ------------------------------------------------------------------
    op.add_column(
        "classification_category",
        sa.Column(
            "budget_role",
            sa.String(16),
            nullable=False,
            server_default="uncategorized",
        ),
    )

    # ------------------------------------------------------------------
    # budgets_budget
    # ------------------------------------------------------------------
    op.create_table(
        "budgets_budget",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column(
            "expected_income_strategy",
            sa.String(32),
            nullable=False,
            server_default="fixed",
        ),
        sa.Column("expected_income", sa.Numeric(19, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("income_rolling_periods", sa.Integer, nullable=False, server_default="3"),
        sa.Column(
            "scope_accounts",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "scope_categories",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "scope_tags",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("pay_period_income_source_id", sa.Uuid(as_uuid=True), nullable=True),
        # EffectiveDatedMixin
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_budget_household", "budgets_budget", ["household_id"])
    op.create_index("ix_budgets_budget_group", "budgets_budget", ["budget_group_id"])
    op.create_index(
        "ix_budgets_budget_group_current",
        "budgets_budget",
        ["budget_group_id"],
        postgresql_where=sa.text("effective_to IS NULL AND archived_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # budgets_budget_line
    # ------------------------------------------------------------------
    op.create_table(
        "budgets_budget_line",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tag_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("planned_amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("rollover_policy", sa.String(24), nullable=False, server_default="none"),
        sa.Column("rollover_cap", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "carried_amount",
            sa.Numeric(19, 4),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_budget_line_budget", "budgets_budget_line", ["budget_id"])
    op.create_index("ix_budgets_budget_line_household", "budgets_budget_line", ["household_id"])

    # ------------------------------------------------------------------
    # budgets_period_actual
    # ------------------------------------------------------------------
    op.create_table(
        "budgets_period_actual",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "budget_line_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("budgets_budget_line.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("planned_amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "actual_amount",
            sa.Numeric(19, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "carried_in",
            sa.Numeric(19, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "carried_out",
            sa.Numeric(19, 4),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_line_id",
            "period_start",
            name="uq_budgets_period_actual_line_period",
        ),
    )
    op.create_index("ix_budgets_period_actual_budget", "budgets_period_actual", ["budget_id"])
    op.create_index("ix_budgets_period_actual_line", "budgets_period_actual", ["budget_line_id"])

    # ------------------------------------------------------------------
    # budgets_period_income
    # ------------------------------------------------------------------
    op.create_table(
        "budgets_period_income",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("expected_income", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_group_id",
            "period_start",
            name="uq_budgets_period_income_group_period",
        ),
    )
    op.create_index("ix_budgets_period_income_group", "budgets_period_income", ["budget_group_id"])

    # updated_at triggers
    for table in (
        "budgets_budget",
        "budgets_budget_line",
        "budgets_period_actual",
        "budgets_period_income",
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
        "budgets_period_income",
        "budgets_period_actual",
        "budgets_budget_line",
        "budgets_budget",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.drop_index("ix_budgets_period_income_group", table_name="budgets_period_income")
    op.drop_table("budgets_period_income")

    op.drop_index("ix_budgets_period_actual_line", table_name="budgets_period_actual")
    op.drop_index("ix_budgets_period_actual_budget", table_name="budgets_period_actual")
    op.drop_table("budgets_period_actual")

    op.drop_index("ix_budgets_budget_line_household", table_name="budgets_budget_line")
    op.drop_index("ix_budgets_budget_line_budget", table_name="budgets_budget_line")
    op.drop_table("budgets_budget_line")

    op.drop_index("ix_budgets_budget_group_current", table_name="budgets_budget")
    op.drop_index("ix_budgets_budget_group", table_name="budgets_budget")
    op.drop_index("ix_budgets_budget_household", table_name="budgets_budget")
    op.drop_table("budgets_budget")

    op.drop_column("classification_category", "budget_role")
