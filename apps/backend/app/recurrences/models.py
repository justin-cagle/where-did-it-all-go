"""SQLAlchemy models for the recurrences domain.

Tables:
  recurrences_recurrence           — confirmed recurring pattern (declared or detected)
  recurrences_candidate            — detected candidate awaiting HITL confirmation
  recurrences_exception            — single-instance override on a recurrence
  recurrences_match                — per-transaction match/deviation/missed record
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


class Recurrence(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A confirmed recurring payment pattern (declared or detected)."""

    __tablename__ = "recurrences_recurrence"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Raw UUID — no FK across module boundary",
    )

    kind: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="detected | declared",
    )
    cadence: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="monthly | weekly | biweekly | semimonthly | annual | custom_cron",
    )

    expected_amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    tolerance: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        comment="Amount variance allowed for matching",
    )

    expected_day_of_period: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Which day of the cadence period payment is expected",
    )
    expected_amount_strategy: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="fixed",
        comment="fixed | last_n_average | manual_estimate | external_signal",
    )

    # Cross-module refs — raw UUIDs, no FK
    linked_category_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Auto-assigns category on match; raw UUID, no FK",
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Optional linked account; raw UUID, no FK",
    )

    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    paused: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        comment="When true: suppresses missed-detection alerts",
    )
    merchant_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    recurrence_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Extra metadata; holds cron string for custom_cron cadence",
    )

    __table_args__ = (
        sa.Index("ix_recurrences_recurrence_household", "household_id"),
        sa.Index("ix_recurrences_recurrence_account", "account_id"),
    )

    def __repr__(self) -> str:
        return (
            f"Recurrence(id={self.id}, kind={self.kind!r}, "
            f"cadence={self.cadence!r}, merchant={self.merchant_name!r})"
        )


class RecurrenceCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Detected recurrence candidate awaiting user confirmation.

    Never auto-promoted to Recurrence. HITL always required.
    """

    __tablename__ = "recurrences_candidate"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    recurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Set when promoted to Recurrence; raw UUID, no FK",
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Raw UUID — no FK across module boundary",
    )

    merchant_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    cadence: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    expected_amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    sample_transaction_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array of transactions_transaction UUIDs used as evidence",
    )
    occurrence_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        comment="pending | confirmed | dismissed",
    )
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    __table_args__ = (
        sa.Index("ix_recurrences_candidate_household", "household_id"),
        sa.Index(
            "ix_recurrences_candidate_pending",
            "household_id",
            postgresql_where=sa.text("status = 'pending'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RecurrenceCandidate(id={self.id}, merchant={self.merchant_name!r}, "
            f"cadence={self.cadence!r}, status={self.status!r})"
        )


class RecurrenceException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-instance override on a recurrence.

    Does not break the series. Three flavors: skip, amount_change, date_shift.
    """

    __tablename__ = "recurrences_exception"

    recurrence_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("recurrences_recurrence.id", ondelete="CASCADE"),
        nullable=False,
    )

    exception_type: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="skip | amount_change | date_shift",
    )
    affected_period: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="The expected period date this exception applies to",
    )

    override_amount: Mapped[Decimal | None] = mapped_column(MONEY_TYPE, nullable=True)
    override_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.Index("ix_recurrences_exception_recurrence", "recurrence_id"),
        sa.UniqueConstraint(
            "recurrence_id",
            "affected_period",
            "exception_type",
            name="uq_recurrences_exception_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RecurrenceException(id={self.id}, "
            f"type={self.exception_type!r}, period={self.affected_period})"
        )


class RecurrenceMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Record of a transaction matched (or missed/deviated) against a recurrence."""

    __tablename__ = "recurrences_match"

    recurrence_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("recurrences_recurrence.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Raw UUID — no FK; NULL for missed instances",
    )

    matched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    deviation_amount: Mapped[Decimal | None] = mapped_column(
        MONEY_TYPE,
        nullable=True,
        comment="Signed diff from expected_amount; NULL when not applicable",
    )
    deviation_days: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Signed diff from expected date in days; NULL when not applicable",
    )

    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="matched | deviated | missed | dismissed",
    )

    expected_date: Mapped[date | None] = mapped_column(
        sa.Date,
        nullable=True,
        comment="The expected period date for this match record",
    )

    __table_args__ = (
        sa.Index("ix_recurrences_match_recurrence", "recurrence_id"),
        sa.Index(
            "ix_recurrences_match_transaction",
            "transaction_id",
            postgresql_where=sa.text("transaction_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RecurrenceMatch(id={self.id}, "
            f"recurrence_id={self.recurrence_id}, status={self.status!r})"
        )
