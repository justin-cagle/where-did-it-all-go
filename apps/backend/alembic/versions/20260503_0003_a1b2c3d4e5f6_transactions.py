"""Transactions domain tables.

Revision ID: a1b2c3d4e5f6
Revises: e2f3a4b5c6d7
Create Date: 2026-05-03 00:00:00.000000

Creates:
  - transactions_transaction       — financial transaction record
  - transactions_split_allocation  — categorization slices over a transaction
  - transactions_payment_group     — logical grouping of related transactions
  - transactions_deduplication_log — dedup candidate pairs awaiting resolution

Self-referential FKs on transactions_transaction (transfer_peer_id,
refund_peer_id) are added via ALTER TABLE after table creation to avoid
circular dependency within op.create_table().

Partial unique index on (account_id, external_id) WHERE external_id IS NOT NULL
enforces Stage 1 exact-match dedup.

Partial index on deduplication_log WHERE resolution = 'pending' speeds up the
HITL queue query.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str | None = "e2f3a4b5c6d7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # transactions_transaction
    # ------------------------------------------------------------------
    op.create_table(
        "transactions_transaction",
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
                name="fk_transactions_transaction_household",
            ),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "accounts_account.id",
                ondelete="CASCADE",
                name="fk_transactions_transaction_account",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
            comment="ISO 4217 currency code",
        ),
        sa.Column(
            "direction",
            sa.String(16),
            nullable=False,
            comment="debit | credit",
        ),
        sa.Column(
            "transaction_type",
            sa.String(16),
            nullable=True,
            comment="payroll|refund|transfer|fee|interest|dividend|regular — null until classifier",
        ),
        sa.Column(
            "state",
            sa.String(16),
            nullable=False,
            server_default="pending",
            comment="pending | posted | reconciled",
        ),
        # Bank-reported dates — no TZ conversion (see data-layer.md)
        sa.Column("posted_date", sa.Date, nullable=False),
        sa.Column("pending_date", sa.Date, nullable=True),
        sa.Column(
            "occurred_at",
            sa.Date,
            nullable=False,
            comment="Bank-reported date; no timezone conversion applied",
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("merchant_name", sa.Text, nullable=True),
        sa.Column(
            "external_id",
            sa.Text,
            nullable=True,
            comment="SimpleFIN/OFX source ID for Stage 1 exact-match dedup",
        ),
        sa.Column(
            "recurrence_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Raw UUID ref to recurrences module; no FK enforced across boundary",
        ),
        sa.Column(
            "manually_categorized",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        # Self-referential peers — added via ALTER TABLE below
        sa.Column("transfer_peer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("refund_peer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transactions_transaction"),
    )
    op.create_index(
        "ix_transactions_transaction_household", "transactions_transaction", ["household_id"]
    )
    op.create_index(
        "ix_transactions_transaction_account", "transactions_transaction", ["account_id"]
    )
    op.create_index("ix_transactions_transaction_state", "transactions_transaction", ["state"])
    op.create_index(
        "ix_transactions_transaction_posted_date", "transactions_transaction", ["posted_date"]
    )
    # Stage 1 dedup: partial unique index on (account_id, external_id)
    op.create_index(
        "uq_transactions_transaction_external_id",
        "transactions_transaction",
        ["account_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER tg_transactions_transaction_updated_at
            BEFORE UPDATE ON transactions_transaction
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )
    # Add self-referential FKs after table creation
    op.create_foreign_key(
        "fk_transactions_transaction_transfer_peer",
        "transactions_transaction",
        "transactions_transaction",
        ["transfer_peer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_transactions_transaction_refund_peer",
        "transactions_transaction",
        "transactions_transaction",
        ["refund_peer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # transactions_split_allocation
    # ------------------------------------------------------------------
    op.create_table(
        "transactions_split_allocation",
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
            "transaction_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "transactions_transaction.id",
                ondelete="CASCADE",
                name="fk_transactions_split_allocation_transaction",
            ),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_transactions_split_allocation_household",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "category_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Raw UUID ref to classification_category; no FK across module boundary",
        ),
        sa.Column(
            "tag_ids",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="JSON array of classification_tag UUIDs",
        ),
        sa.Column(
            "attributed_to_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_user.id",
                ondelete="SET NULL",
                name="fk_transactions_split_allocation_user",
            ),
            nullable=True,
        ),
        sa.Column(
            "manually_categorized",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "rule_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Raw UUID ref to classification rule; no FK across module boundary",
        ),
        sa.Column("rule_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transactions_split_allocation"),
    )
    op.create_index(
        "ix_transactions_split_allocation_transaction",
        "transactions_split_allocation",
        ["transaction_id"],
    )
    op.create_index(
        "ix_transactions_split_allocation_household",
        "transactions_split_allocation",
        ["household_id"],
    )
    op.execute(
        """
        CREATE TRIGGER tg_transactions_split_allocation_updated_at
            BEFORE UPDATE ON transactions_split_allocation
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # transactions_payment_group
    # ------------------------------------------------------------------
    op.create_table(
        "transactions_payment_group",
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
                name="fk_transactions_payment_group_household",
            ),
            nullable=False,
        ),
        sa.Column(
            "group_type",
            sa.String(32),
            nullable=False,
            comment="split_purchase | split_funding",
        ),
        sa.Column(
            "member_transaction_ids",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="JSON array of transactions_transaction UUIDs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transactions_payment_group"),
    )
    op.create_index(
        "ix_transactions_payment_group_household",
        "transactions_payment_group",
        ["household_id"],
    )
    op.execute(
        """
        CREATE TRIGGER tg_transactions_payment_group_updated_at
            BEFORE UPDATE ON transactions_payment_group
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # transactions_deduplication_log
    # ------------------------------------------------------------------
    op.create_table(
        "transactions_deduplication_log",
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
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_transactions_dedup_log_household",
            ),
            nullable=False,
        ),
        sa.Column(
            "candidate_a_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "transactions_transaction.id",
                ondelete="CASCADE",
                name="fk_transactions_dedup_log_candidate_a",
            ),
            nullable=False,
        ),
        sa.Column(
            "candidate_b_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "transactions_transaction.id",
                ondelete="CASCADE",
                name="fk_transactions_dedup_log_candidate_b",
            ),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            comment="0.0000-1.0000 fuzzy match confidence",
        ),
        sa.Column("match_reason", sa.Text, nullable=False),
        sa.Column(
            "resolution",
            sa.String(16),
            nullable=False,
            server_default="pending",
            comment="pending | merged | rejected",
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transactions_deduplication_log"),
    )
    op.create_index(
        "ix_transactions_deduplication_log_household",
        "transactions_deduplication_log",
        ["household_id"],
    )
    op.create_index(
        "ix_transactions_deduplication_log_pending",
        "transactions_deduplication_log",
        ["household_id"],
        postgresql_where=sa.text("resolution = 'pending'"),
    )
    op.execute(
        """
        CREATE TRIGGER tg_transactions_deduplication_log_updated_at
            BEFORE UPDATE ON transactions_deduplication_log
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS tg_transactions_deduplication_log_updated_at "
        "ON transactions_deduplication_log"
    )
    op.drop_index(
        "ix_transactions_deduplication_log_pending",
        table_name="transactions_deduplication_log",
    )
    op.drop_index(
        "ix_transactions_deduplication_log_household",
        table_name="transactions_deduplication_log",
    )
    op.drop_table("transactions_deduplication_log")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_transactions_payment_group_updated_at "
        "ON transactions_payment_group"
    )
    op.drop_index(
        "ix_transactions_payment_group_household", table_name="transactions_payment_group"
    )
    op.drop_table("transactions_payment_group")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_transactions_split_allocation_updated_at "
        "ON transactions_split_allocation"
    )
    op.drop_index(
        "ix_transactions_split_allocation_household",
        table_name="transactions_split_allocation",
    )
    op.drop_index(
        "ix_transactions_split_allocation_transaction",
        table_name="transactions_split_allocation",
    )
    op.drop_table("transactions_split_allocation")

    # Drop self-referential FKs before dropping the table
    op.drop_constraint(
        "fk_transactions_transaction_refund_peer",
        "transactions_transaction",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_transactions_transaction_transfer_peer",
        "transactions_transaction",
        type_="foreignkey",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS tg_transactions_transaction_updated_at ON transactions_transaction"
    )
    op.drop_index("uq_transactions_transaction_external_id", table_name="transactions_transaction")
    op.drop_index("ix_transactions_transaction_posted_date", table_name="transactions_transaction")
    op.drop_index("ix_transactions_transaction_state", table_name="transactions_transaction")
    op.drop_index("ix_transactions_transaction_account", table_name="transactions_transaction")
    op.drop_index("ix_transactions_transaction_household", table_name="transactions_transaction")
    op.drop_table("transactions_transaction")
