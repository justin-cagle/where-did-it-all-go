"""Classification domain tables.

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 00:00:00.000000

Creates:
  - classification_category             -- 2-level category tree (system + household-scoped)
  - classification_tag                  -- flat tags, household-scoped
  - classification_rule                 -- user-defined rules with JSONB conditions/actions
  - classification_income_source        -- known income streams for payroll matching
  - classification_household_settings   -- per-household pipeline config (strictness)

Seeds system categories (Transfer, Uncategorized, Income, Refund) into
classification_category with household_id=NULL, system=true, deletable=false,
renameable=false. These are global rows shared across all households.

Self-referential FK on classification_category.parent_id uses ondelete=SET NULL
so archiving a parent sets children's parent_id to NULL rather than cascading.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "f1e2d3c4b5a6"  # pragma: allowlist secret
down_revision: str | None = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# System category seeds
_SYSTEM_CATEGORIES = [
    {"name": "Transfer", "sort_order": 0},
    {"name": "Uncategorized", "sort_order": 1},
    {"name": "Income", "sort_order": 2},
    {"name": "Refund", "sort_order": 3},
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # classification_category
    # ------------------------------------------------------------------
    op.create_table(
        "classification_category",
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
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deletable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("renameable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Self-referential FK added after table creation to avoid circular dependency
    op.create_foreign_key(
        "fk_classification_category_parent",
        "classification_category",
        "classification_category",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_classification_category_household",
        "classification_category",
        ["household_id"],
    )
    op.create_index(
        "ix_classification_category_parent",
        "classification_category",
        ["parent_id"],
    )

    # ------------------------------------------------------------------
    # classification_tag
    # ------------------------------------------------------------------
    op.create_table(
        "classification_tag",
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
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_tag_household",
        "classification_tag",
        ["household_id"],
    )

    # ------------------------------------------------------------------
    # classification_rule
    # ------------------------------------------------------------------
    op.create_table(
        "classification_rule",
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
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("conditions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("actions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="auto_apply"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_rule_household",
        "classification_rule",
        ["household_id"],
    )
    op.create_index(
        "ix_classification_rule_priority_order",
        "classification_rule",
        ["household_id", "priority", "created_at"],
    )

    # ------------------------------------------------------------------
    # classification_income_source
    # ------------------------------------------------------------------
    op.create_table(
        "classification_income_source",
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
        sa.Column("attributed_to_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("employer_name", sa.Text(), nullable=False),
        sa.Column("sub_type", sa.String(32), nullable=False),
        sa.Column("expected_cadence", sa.Text(), nullable=True),
        sa.Column(
            "expected_amount_min",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
        ),
        sa.Column(
            "expected_amount_max",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("variability_model", sa.String(32), nullable=False, server_default="fixed"),
        sa.Column("deposit_split_pattern", JSONB(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attributed_to_user_id"],
            ["households_user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_income_source_household",
        "classification_income_source",
        ["household_id"],
    )

    # ------------------------------------------------------------------
    # classification_household_settings
    # ------------------------------------------------------------------
    op.create_table(
        "classification_household_settings",
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
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False, unique=True),
        sa.Column("strictness", sa.String(16), nullable=False, server_default="strict"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_household_settings_household",
        "classification_household_settings",
        ["household_id"],
    )

    # ------------------------------------------------------------------
    # Seed system categories (global — household_id NULL)
    # ------------------------------------------------------------------
    cat_table = sa.table(
        "classification_category",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.Text),
        sa.column("household_id", sa.Uuid),
        sa.column("parent_id", sa.Uuid),
        sa.column("system", sa.Boolean),
        sa.column("deletable", sa.Boolean),
        sa.column("renameable", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        cat_table,
        [
            {
                "id": uuid.uuid4(),
                "name": entry["name"],
                "household_id": None,
                "parent_id": None,
                "system": True,
                "deletable": False,
                "renameable": False,
                "sort_order": entry["sort_order"],
            }
            for entry in _SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_table("classification_household_settings")
    op.drop_table("classification_income_source")
    op.drop_table("classification_rule")
    op.drop_table("classification_tag")
    # Drop FK before table to avoid dependency errors
    op.drop_constraint(
        "fk_classification_category_parent", "classification_category", type_="foreignkey"
    )
    op.drop_table("classification_category")
