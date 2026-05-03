"""Accounts domain tables.

Revision ID: e2f3a4b5c6d7
Revises: c4e9f2a8b1d6
Create Date: 2026-05-03 00:00:00.000000

Creates:
  - accounts_account_group   — logical grouping for multi-feed accounts
  - accounts_account         — base financial account entity
  - accounts_manual_account  — annotation: account is manually maintained
  - accounts_debt_account    — annotation: account has debt-specific metadata
  - accounts_debt_balance    — APR tranche with effective-dated history

Adds updated_at triggers on all tables.
Adds partial index on accounts_debt_balance for the current row (effective_to IS NULL).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "e2f3a4b5c6d7"  # pragma: allowlist secret
down_revision: str | None = "c4e9f2a8b1d6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # accounts_account_group
    # ------------------------------------------------------------------
    op.create_table(
        "accounts_account_group",
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
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_accounts_account_group_household",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "primary_holder_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_user.id",
                ondelete="SET NULL",
                name="fk_accounts_account_group_primary_holder",
            ),
            nullable=True,
        ),
        sa.Column(
            "authorized_user_ids",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="JSON array of user UUIDs who are authorized users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accounts_account_group"),
    )
    op.create_index(
        "ix_accounts_account_group_household", "accounts_account_group", ["household_id"]
    )
    op.execute(
        """
        CREATE TRIGGER tg_accounts_account_group_updated_at
            BEFORE UPDATE ON accounts_account_group
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # accounts_account
    # ------------------------------------------------------------------
    op.create_table(
        "accounts_account",
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
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_accounts_account_household",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("institution", sa.String(255), nullable=True),
        sa.Column(
            "account_type",
            sa.String(32),
            nullable=False,
            comment="checking|savings|credit_card|investment|loan|line_of_credit|manual|other",
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
            comment="ISO 4217 currency code",
        ),
        sa.Column(
            "current_balance",
            sa.Numeric(precision=19, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_manual",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "account_group_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "accounts_account_group.id",
                ondelete="SET NULL",
                name="fk_accounts_account_group",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accounts_account"),
    )
    op.create_index("ix_accounts_account_household", "accounts_account", ["household_id"])
    op.create_index("ix_accounts_account_type", "accounts_account", ["account_type"])
    op.create_index("ix_accounts_account_group", "accounts_account", ["account_group_id"])
    op.execute(
        """
        CREATE TRIGGER tg_accounts_account_updated_at
            BEFORE UPDATE ON accounts_account
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # accounts_manual_account
    # ------------------------------------------------------------------
    op.create_table(
        "accounts_manual_account",
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
        sa.Column(
            "account_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "accounts_account.id",
                ondelete="CASCADE",
                name="fk_accounts_manual_account_account",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accounts_manual_account"),
        sa.UniqueConstraint("account_id", name="uq_accounts_manual_account_account"),
    )
    op.create_index(
        "ix_accounts_manual_account_account",
        "accounts_manual_account",
        ["account_id"],
        unique=True,
    )
    op.execute(
        """
        CREATE TRIGGER tg_accounts_manual_account_updated_at
            BEFORE UPDATE ON accounts_manual_account
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # accounts_debt_account
    # ------------------------------------------------------------------
    op.create_table(
        "accounts_debt_account",
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
        sa.Column(
            "account_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "accounts_account.id",
                ondelete="CASCADE",
                name="fk_accounts_debt_account_account",
            ),
            nullable=False,
        ),
        sa.Column(
            "minimum_payment_strategy",
            sa.String(32),
            nullable=False,
            server_default="from_statement",
            comment="fixed_amount|percentage_of_balance|from_statement",
        ),
        sa.Column(
            "statement_day",
            sa.SmallInteger,
            nullable=True,
            comment="Day of month (1-28) when statement closes",
        ),
        sa.Column(
            "due_day",
            sa.SmallInteger,
            nullable=True,
            comment="Day of month (1-28) when payment is due",
        ),
        sa.Column("payoff_target_date", sa.Date, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_accounts_debt_account"),
        sa.UniqueConstraint("account_id", name="uq_accounts_debt_account_account"),
    )
    op.create_index(
        "ix_accounts_debt_account_account",
        "accounts_debt_account",
        ["account_id"],
        unique=True,
    )
    op.execute(
        """
        CREATE TRIGGER tg_accounts_debt_account_updated_at
            BEFORE UPDATE ON accounts_debt_account
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # accounts_debt_balance
    # ------------------------------------------------------------------
    op.create_table(
        "accounts_debt_balance",
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
        # Effective-dated versioning (data-layer.md — Versioning)
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column(
            "effective_to",
            sa.Date,
            nullable=True,
            comment="NULL = current version",
        ),
        sa.Column(
            "debt_account_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "accounts_debt_account.id",
                ondelete="CASCADE",
                name="fk_accounts_debt_balance_debt_account",
            ),
            nullable=False,
        ),
        sa.Column("principal_balance", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "apr",
            sa.Numeric(precision=7, scale=6),
            nullable=False,
            comment="APR as decimal fraction: 0.2499 = 24.99%",
        ),
        sa.Column(
            "term",
            sa.Integer,
            nullable=True,
            comment="Loan term in months",
        ),
        sa.Column("promotional_period_end", sa.Date, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_accounts_debt_balance"),
    )
    op.create_index(
        "ix_accounts_debt_balance_debt_account", "accounts_debt_balance", ["debt_account_id"]
    )
    op.create_index(
        "ix_accounts_debt_balance_current",
        "accounts_debt_balance",
        ["debt_account_id"],
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER tg_accounts_debt_balance_updated_at
            BEFORE UPDATE ON accounts_debt_balance
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS tg_accounts_debt_balance_updated_at ON accounts_debt_balance"
    )
    op.drop_index("ix_accounts_debt_balance_current", table_name="accounts_debt_balance")
    op.drop_index("ix_accounts_debt_balance_debt_account", table_name="accounts_debt_balance")
    op.drop_table("accounts_debt_balance")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_accounts_debt_account_updated_at ON accounts_debt_account"
    )
    op.drop_index("ix_accounts_debt_account_account", table_name="accounts_debt_account")
    op.drop_table("accounts_debt_account")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_accounts_manual_account_updated_at ON accounts_manual_account"
    )
    op.drop_index("ix_accounts_manual_account_account", table_name="accounts_manual_account")
    op.drop_table("accounts_manual_account")

    op.execute("DROP TRIGGER IF EXISTS tg_accounts_account_updated_at ON accounts_account")
    op.drop_index("ix_accounts_account_group", table_name="accounts_account")
    op.drop_index("ix_accounts_account_type", table_name="accounts_account")
    op.drop_index("ix_accounts_account_household", table_name="accounts_account")
    op.drop_table("accounts_account")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_accounts_account_group_updated_at ON accounts_account_group"
    )
    op.drop_index("ix_accounts_account_group_household", table_name="accounts_account_group")
    op.drop_table("accounts_account_group")
