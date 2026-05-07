"""SQLAlchemy models for the debts domain.

Tables:
  debts_debt_plan           -- versioned payoff strategy (effective-dated rows)
  debts_debt_plan_schedule  -- per-account per-month amortization cache
  debts_debt_plan_summary   -- aggregate totals / payoff stats cache

Versioning pattern:
  DebtPlan rows use EffectiveDatedMixin (effective_from / effective_to).
  plan_group_id groups all versions of the same logical plan -- first version
  has plan_group_id == id; subsequent edits share the same plan_group_id.
  API routes use plan_group_id as the external plan identifier.

  Schedule and summary rows reference plan_id (version-specific) and are
  regenerated whenever the active plan version changes.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import (
    EffectiveDatedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.platform.money import CURRENCY_TYPE, MONEY_TYPE


class DebtPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, EffectiveDatedMixin):
    """Time-versioned household debt payoff strategy.

    Each edit creates a new version row (new id, new effective_from, effective_to=NULL);
    the prior row gets effective_to set to the day before the new version's effective_from.
    """

    __tablename__ = "debts_debt_plan"

    plan_group_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Groups all versions of the same logical plan. First version: == id.",
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    method: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="avalanche | snowball | custom | none",
    )
    monthly_extra_payment: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    snowball_flow: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
        comment="Redirect paid-off account minimum to next priority account",
    )
    account_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        comment="Ordered list of DebtAccount UUIDs covered by this plan",
    )

    __table_args__ = (
        sa.Index("ix_debts_debt_plan_household", "household_id"),
        sa.Index("ix_debts_debt_plan_group", "plan_group_id"),
        sa.Index(
            "ix_debts_debt_plan_group_current",
            "plan_group_id",
            postgresql_where=sa.text("effective_to IS NULL AND archived_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DebtPlan(id={self.id}, group={self.plan_group_id}, "
            f"name={self.name!r}, method={self.method!r})"
        )


class DebtPlanSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One month's amortization row for one account within a plan version.

    Derived/cached -- recomputable from the plan + current balances at any time.
    No soft delete -- rows are replaced on recompute.
    """

    __tablename__ = "debts_debt_plan_schedule"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("debts_debt_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="DebtAccount UUID -- no FK, cross-module boundary",
    )
    period_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="First day of the payment period (month)",
    )
    opening_balance: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    payment: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    principal: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    interest: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    is_payoff: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )

    __table_args__ = (
        sa.Index("ix_debts_schedule_plan", "plan_id"),
        sa.Index("ix_debts_schedule_household", "household_id"),
        sa.Index("ix_debts_schedule_account", "account_id"),
        sa.UniqueConstraint(
            "plan_id",
            "account_id",
            "period_date",
            name="uq_debts_schedule_plan_account_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DebtPlanSchedule(id={self.id}, account={self.account_id}, "
            f"period={self.period_date}, closing={self.closing_balance})"
        )


class DebtPlanSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aggregate payoff statistics for a plan version.

    Derived/cached alongside schedule. No soft delete.
    """

    __tablename__ = "debts_debt_plan_summary"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("debts_debt_plan.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    total_interest: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    total_paid: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    months_to_payoff: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    interest_savings_vs_minimums: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    payoff_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    __table_args__ = (sa.Index("ix_debts_summary_plan", "plan_id", unique=True),)

    def __repr__(self) -> str:
        return (
            f"DebtPlanSummary(id={self.id}, plan={self.plan_id}, "
            f"months={self.months_to_payoff}, payoff={self.payoff_date})"
        )
