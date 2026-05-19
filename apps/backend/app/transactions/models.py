"""SQLAlchemy models for the transactions domain.

Tables:
  transactions_transaction       — financial transaction record
  transactions_split_allocation  — categorization slice over a transaction
  transactions_payment_group     — logical grouping of related transactions
  transactions_deduplication_log — dedup candidate pairs awaiting resolution
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.money import CURRENCY_TYPE, MONEY_TYPE
from app.platform.time import utcnow


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A single financial transaction on an account."""

    __tablename__ = "transactions_transaction"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_account.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Money
    amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    # Classification
    direction: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="debit | credit",
    )
    transaction_type: Mapped[str | None] = mapped_column(
        sa.String(16),
        nullable=True,
        comment="payroll|refund|transfer|fee|interest|dividend|regular — null until classifier",
    )
    state: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        comment="pending | posted | reconciled",
    )

    # Dates (bank-reported — no TZ conversion; see data-layer.md)
    posted_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    pending_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    occurred_at: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="Bank-reported transaction date; no TZ conversion applied",
    )

    # Description
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Ingest
    external_id: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="SimpleFIN/OFX source ID used for exact-match dedup",
    )

    # Cross-module refs stored as raw UUIDs (no FK — modules are not joined)
    recurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Populated by recurrences module; no FK enforced across module boundary",
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Cross-module ref to ingest_import_job; no FK enforced",
    )

    manually_categorized: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )

    # Self-referential peers (added via ALTER TABLE after table creation)
    transfer_peer_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="FK to self — linked transfer counterpart",
    )
    refund_peer_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="FK to self — linked refund counterpart",
    )

    __table_args__ = (
        sa.Index("ix_transactions_transaction_household", "household_id"),
        sa.Index("ix_transactions_transaction_account", "account_id"),
        sa.Index("ix_transactions_transaction_state", "state"),
        sa.Index("ix_transactions_transaction_posted_date", "posted_date"),
        sa.Index("ix_transactions_transaction_import_job", "import_job_id"),
        # Partial unique index for external_id dedup (Stage 1)
        sa.Index(
            "uq_transactions_transaction_external_id",
            "account_id",
            "external_id",
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id}, amount={self.amount} {self.currency}, "
            f"state={self.state!r}, direction={self.direction!r})"
        )


class SplitAllocation(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Categorization slice applied over a transaction amount.

    Every transaction has at least one split. A transaction with no explicit
    splits gets an implicit single allocation for the full amount with no
    category (uncategorized). sum(split.amount) always equals transaction.amount.
    """

    __tablename__ = "transactions_split_allocation"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("transactions_transaction.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Money
    amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    # Cross-module refs (raw UUIDs — classification module owns these tables)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="FK to classification_category — stored as raw UUID, no JOIN enforced",
    )
    tag_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="JSON array of classification_tag UUIDs",
    )

    attributed_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    manually_categorized: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    # Rule provenance (raw UUIDs — classification module owns rules)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Which rule fired; raw UUID, no FK across module boundary",
    )
    rule_fired_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.Index("ix_transactions_split_allocation_transaction", "transaction_id"),
        sa.Index("ix_transactions_split_allocation_household", "household_id"),
    )

    def __repr__(self) -> str:
        return f"SplitAllocation(id={self.id}, amount={self.amount} {self.currency})"


class PaymentGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Logical grouping of transactions that constitute a single spend event.

    Confirmed by HITL after heuristic detection. Members retain per-account
    attribution; the group is treated as a single logical event for reporting.
    """

    __tablename__ = "transactions_payment_group"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="split_purchase | split_funding",
    )
    member_transaction_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="JSON array of transactions_transaction UUIDs",
    )

    __table_args__ = (sa.Index("ix_transactions_payment_group_household", "household_id"),)

    def __repr__(self) -> str:
        return f"PaymentGroup(id={self.id}, type={self.group_type!r})"


class DeduplicationLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Record of a candidate dedup pair and its resolution.

    Written when fuzzy matching detects possible duplicates. Resolution is
    either HITL (pending) or auto-merged (when source=simplefin, confidence
    above threshold). No soft delete — this is an audit-like log.
    """

    __tablename__ = "transactions_deduplication_log"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_a_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("transactions_transaction.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_b_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("transactions_transaction.id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        sa.Numeric(precision=5, scale=4, asdecimal=True),
        nullable=False,
    )
    match_reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    resolution: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        comment="pending | merged | rejected",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_transactions_deduplication_log_household", "household_id"),
        sa.Index(
            "ix_transactions_deduplication_log_pending",
            "household_id",
            postgresql_where=sa.text("resolution = 'pending'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DeduplicationLog(id={self.id}, "
            f"confidence={self.confidence}, resolution={self.resolution!r})"
        )


# Satisfy F401 for the utcnow import used indirectly via default= in other modules
__all__: list[Any] = [
    "DeduplicationLog",
    "PaymentGroup",
    "SplitAllocation",
    "Transaction",
    "utcnow",
]
