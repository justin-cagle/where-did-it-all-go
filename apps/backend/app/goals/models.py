"""SQLAlchemy models for the goals domain.

Tables:
  goals_goal              -- household goal with type + completion policy
  goals_funding_source    -- per-goal funding source (account / income / surplus)
  goals_contribution      -- recorded contribution events (manual/tag/recurring)
  goals_snapshot          -- computed burn-up snapshot (cached, recalculated on demand)
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


class Goal(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A household financial goal.

    goal_type determines which optional fields apply:
      debt_payoff          -> linked_debt_plan_id
      category_reduction   -> linked_category_id
      minimum_balance      -> minimum_balance_threshold
    """

    __tablename__ = "goals_goal"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    goal_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="savings_target | purchase | debt_payoff | net_worth | category_reduction | "
        "emergency_fund | recurring_contribution | minimum_balance",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="active",
        server_default=sa.text("'active'"),
        comment="active | paused | completed | archived",
    )
    target_amount: Mapped[Decimal | None] = mapped_column(MONEY_TYPE, nullable=True)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    target_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    funding_strategy: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="virtual_allocation",
        server_default=sa.text("'virtual_allocation'"),
        comment="dedicated_account | virtual_allocation",
    )
    completion_policy: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="prompt_on_complete",
        server_default=sa.text("'prompt_on_complete'"),
        comment="archive_on_complete | prompt_on_complete | auto_extend | auto_clone | "
        "convert_to_recurring",
    )
    auto_extend_amount: Mapped[Decimal | None] = mapped_column(
        MONEY_TYPE,
        nullable=True,
        comment="Used by auto_extend completion policy",
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL = household-owned goal",
    )
    linked_debt_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="For debt_payoff type -- no FK (cross-module boundary)",
    )
    linked_category_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="For category_reduction type -- no FK (cross-module boundary)",
    )
    minimum_balance_threshold: Mapped[Decimal | None] = mapped_column(
        MONEY_TYPE,
        nullable=True,
        comment="For minimum_balance type",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Type-specific config (e.g. gap thresholds, tag_id for tag-driven goals)",
    )

    __table_args__ = (
        sa.Index("ix_goals_goal_household", "household_id"),
        sa.Index("ix_goals_goal_household_status", "household_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"Goal(id={self.id}, name={self.name!r}, type={self.goal_type!r}, "
            f"status={self.status!r})"
        )


class GoalFundingSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Funding source attached to a goal.

    No soft delete -- funding sources are removed by DELETE when the user
    detaches them. Cascade deletes when the goal is hard-deleted.
    """

    __tablename__ = "goals_funding_source"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("goals_goal.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="account | income_stream | household_surplus",
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="account_id or income_source_id -- no FK (cross-module boundary)",
    )
    attributed_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        sa.Index("ix_goals_funding_source_goal", "goal_id"),
        sa.Index("ix_goals_funding_source_household", "household_id"),
    )

    def __repr__(self) -> str:
        return f"GoalFundingSource(id={self.id}, goal={self.goal_id}, type={self.source_type!r})"


class GoalContribution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A recorded contribution event toward a goal.

    transaction_id is stored without FK to avoid cross-module joins.
    Idempotency: tag_driven contributions check transaction_id before inserting.
    """

    __tablename__ = "goals_contribution"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("goals_goal.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    contributed_at: Mapped[date] = mapped_column(sa.Date, nullable=False)
    contribution_type: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="manual | tag_driven | recurring_rule",
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Source transaction -- no FK (cross-module boundary)",
    )
    attributed_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.Index("ix_goals_contribution_goal", "goal_id"),
        sa.Index("ix_goals_contribution_household", "household_id"),
        sa.Index("ix_goals_contribution_transaction", "transaction_id"),
        sa.Index(
            "uq_goals_contribution_goal_transaction",
            "goal_id",
            "transaction_id",
            unique=True,
            postgresql_where=sa.text("transaction_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"GoalContribution(id={self.id}, goal={self.goal_id}, "
            f"amount={self.amount}, type={self.contribution_type!r})"
        )


class GoalSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Computed burn-up snapshot for a goal at a point in time.

    Derived/cached -- recomputed by compute_burn_up(). No soft delete.
    Multiple rows per goal: one per compute_burn_up() call.
    """

    __tablename__ = "goals_snapshot"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("goals_goal.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    cumulative_actual: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    cumulative_expected: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    required_pace: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        comment="Monthly contribution rate needed to hit target on time",
    )
    actual_pace: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        comment="Trailing 30-day contribution rate",
    )
    projected_completion_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    gap_to_close: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        comment="cumulative_expected - cumulative_actual; negative = ahead",
    )
    progress_pct: Mapped[Decimal] = mapped_column(
        sa.Numeric(precision=7, scale=4, asdecimal=True),
        nullable=False,
        comment="cumulative_actual / target_amount * 100; uncapped",
    )
    burn_up_status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="ahead | on_track | behind | at_risk | off_track",
    )
    computed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_goals_snapshot_goal", "goal_id"),
        sa.Index("ix_goals_snapshot_goal_date", "goal_id", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return (
            f"GoalSnapshot(id={self.id}, goal={self.goal_id}, "
            f"date={self.snapshot_date}, pct={self.progress_pct}, "
            f"status={self.burn_up_status!r})"
        )
