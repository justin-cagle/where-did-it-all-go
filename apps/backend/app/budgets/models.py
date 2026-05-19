"""SQLAlchemy models for the budgets domain.

Tables:
  budgets_budget              -- versioned budget plan (effective-dated rows)
  budgets_budget_line         -- per-category allocation within a budget
  budgets_period_actual       -- computed/cached actuals per line per period
  budgets_period_income       -- manual_per_period income overrides (budget-level)

Versioning pattern:
  Budget rows use EffectiveDatedMixin (effective_from / effective_to).
  budget_group_id groups all versions of the same logical budget — first version
  has budget_group_id == id; subsequent edits share the same budget_group_id.
  BudgetLine.budget_id references budget_group_id (stable across versions).
  API routes use budget_group_id as the external budget identifier.
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


class Budget(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, EffectiveDatedMixin):
    """Time-bounded household budget plan, versioned via effective-dated rows.

    Each edit creates a new version row (new id, new effective_from, effective_to=NULL);
    the prior row gets effective_to set to the day before the new version's effective_from.
    Multiple concurrent budgets per household are supported.
    """

    __tablename__ = "budgets_budget"

    # Stable logical ID across all versions of this budget
    budget_group_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Groups all versions of the same logical budget. First version: == id.",
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL = household-owned; set for personal budgets",
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    period: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="monthly | weekly | biweekly | semimonthly | annual | custom",
    )
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    method: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="zero_based | envelope | fifty_thirty_twenty | percentage_based"
        " | rolling_average | manual | none",
    )
    expected_income_strategy: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="fixed",
        comment="fixed | from_income_sources | last_period_actual | rolling_average"
        " | manual_per_period",
    )
    expected_income: Mapped[Decimal | None] = mapped_column(MONEY_TYPE, nullable=True)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    income_rolling_periods: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=3)

    # Scope filters — empty list means "any" on that dimension
    scope_accounts: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        comment="List of account UUIDs; empty = any account",
    )
    scope_categories: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        comment="List of category UUIDs; empty = any category",
    )
    scope_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        comment="List of tag UUIDs; empty = any tag",
    )

    pay_period_income_source_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Raw UUID — no FK; drives pay-period boundary alignment from IncomeSource cadence",
    )

    __table_args__ = (
        sa.Index("ix_budgets_budget_household", "household_id"),
        sa.Index("ix_budgets_budget_group", "budget_group_id"),
        sa.Index(
            "ix_budgets_budget_group_current",
            "budget_group_id",
            postgresql_where=sa.text("effective_to IS NULL AND archived_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Budget(id={self.id}, group={self.budget_group_id}, "
            f"name={self.name!r}, method={self.method!r})"
        )


class BudgetLine(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """One planned category (or category+tag) allocation within a budget.

    budget_id references budget_group_id — stable across all versions of the budget.
    """

    __tablename__ = "budgets_budget_line"

    # References budget_group_id (stable logical budget ID, not version-specific)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="References Budget.budget_group_id — stable across versions",
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Cross-module refs — raw UUIDs, no FK enforced across module boundary
    category_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="classification_category UUID; raw UUID, no FK",
    )
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="classification_tag UUID; narrows line to category+tag intersection",
    )

    planned_amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    rollover_policy: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        default="none",
        comment="none | accumulate | accumulate_capped | debt_carry | reset_on_overspend",
    )
    rollover_cap: Mapped[Decimal | None] = mapped_column(
        MONEY_TYPE,
        nullable=True,
        comment="Maximum carryover allowed for accumulate_capped policy",
    )
    carried_amount: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
        comment="Running carried balance from prior periods; updated on period close",
    )

    __table_args__ = (
        sa.Index("ix_budgets_budget_line_budget", "budget_id"),
        sa.Index("ix_budgets_budget_line_household", "household_id"),
    )

    def __repr__(self) -> str:
        return (
            f"BudgetLine(id={self.id}, category={self.category_id}, "
            f"planned={self.planned_amount} {self.currency})"
        )


class BudgetPeriodActual(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Computed/cached actuals for one budget line over one period.

    Derived from SplitAllocations — safe to recompute at any time.
    Source of truth is always the SplitAllocation rows; these are a cache.
    No soft delete — rows are replaced on recompute.
    """

    __tablename__ = "budgets_period_actual"

    # Both reference stable budget_group_id / line.id
    budget_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="References Budget.budget_group_id",
    )
    budget_line_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("budgets_budget_line.id", ondelete="CASCADE"),
        nullable=False,
    )

    period_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    period_end: Mapped[date] = mapped_column(sa.Date, nullable=False)

    planned_amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    actual_amount: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    carried_in: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    carried_out: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    has_approximate_fx: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("FALSE"),
        comment="True when any allocation in this period used a fallback FX rate",
    )

    __table_args__ = (
        sa.Index("ix_budgets_period_actual_budget", "budget_id"),
        sa.Index("ix_budgets_period_actual_line", "budget_line_id"),
        sa.UniqueConstraint(
            "budget_line_id",
            "period_start",
            name="uq_budgets_period_actual_line_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"BudgetPeriodActual(id={self.id}, line={self.budget_line_id}, "
            f"period={self.period_start}..{self.period_end})"
        )


class BudgetPeriodIncome(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-period income override for the manual_per_period strategy.

    Budget-group-scoped (persists across version edits).
    Created or updated via POST /{id}/income.
    """

    __tablename__ = "budgets_period_income"

    budget_group_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="References Budget.budget_group_id",
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expected_income: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")

    __table_args__ = (
        sa.Index("ix_budgets_period_income_group", "budget_group_id"),
        sa.UniqueConstraint(
            "budget_group_id",
            "period_start",
            name="uq_budgets_period_income_group_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"BudgetPeriodIncome(id={self.id}, group={self.budget_group_id}, "
            f"period={self.period_start}, income={self.expected_income} {self.currency})"
        )
