"""SQLAlchemy models for the projections domain.

Tables:
  projections_scenario        -- named or transient what-if scenario
  projections_run             -- metadata for a completed projection run
  projections_event           -- projected cash-flow event (output of the engine)
  projections_breach_event    -- balance/limit/goal breach event
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


class ProjectionScenario(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A named or transient what-if scenario.

    saved=False (default): transient session; cleaned up by a daily ARQ job after 24h.
    saved=True: retained until the user deletes it.
    overrides: JSON delta list applied on top of base projection inputs.
    """

    __tablename__ = "projections_scenario"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="NULL = unsaved/transient scenario",
    )
    overrides: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
        comment="List of override delta dicts; see OverrideType enum",
    )
    base_run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="FK to projections_run (nullable); no FK constraint (created after run)",
    )
    saved: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
        comment="True = user explicitly saved this scenario",
    )

    __table_args__ = (
        sa.Index("ix_projections_scenario_household", "household_id"),
        sa.Index(
            "ix_projections_scenario_household_saved",
            "household_id",
            "saved",
        ),
    )

    def __repr__(self) -> str:
        return f"ProjectionScenario(id={self.id}, name={self.name!r}, saved={self.saved})"


class ProjectionRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metadata record for one projection computation.

    Cached: if a run with matching (inputs_hash, as_of_date, horizon_months,
    scenario_id) exists and expires_at > now, its events are returned directly.
    """

    __tablename__ = "projections_run"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="NULL = base projection (no scenario); no FK (scenario may be transient)",
    )
    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    horizon_months: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="SHA-256 of serialized canonical inputs; used for cache validation",
    )
    computed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        comment="Cache expiry; invalidated by domain event handlers",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        server_default=sa.text("'pending'"),
        comment="pending | complete | failed",
    )

    __table_args__ = (
        sa.Index("ix_projections_run_household", "household_id"),
        sa.Index(
            "ix_projections_run_cache_key",
            "household_id",
            "inputs_hash",
            "as_of_date",
            "horizon_months",
            "scenario_id",
        ),
    )

    def __repr__(self) -> str:
        return f"ProjectionRun(id={self.id}, as_of={self.as_of_date}, status={self.status!r})"


class ProjectedEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One projected cash-flow event produced by the projection engine.

    Belongs to a single run (run_id). Deleted and regenerated on recompute.
    scenario_id=NULL means base projection.
    source_id + source_type identify the originating entity (recurrence, budget line,
    debt plan, goal).
    """

    __tablename__ = "projections_event"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("projections_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="NULL = base projection; no FK (scenario may be transient)",
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Raw UUID; no FK (cross-module boundary)",
    )
    event_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    event_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="recurrence | budget_spend | debt_payment | goal_contribution | "
        "income | balance_breach | goal_milestone",
    )
    amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False)
    direction: Mapped[str] = mapped_column(
        sa.String(8),
        nullable=False,
        comment="debit | credit",
    )
    confidence: Mapped[str] = mapped_column(
        sa.String(8),
        nullable=False,
        comment="high | medium | low",
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="recurrence_id | budget_line_id | debt_plan_id | goal_id",
    )
    source_type: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
    )

    __table_args__ = (
        sa.Index("ix_projections_event_run", "run_id"),
        sa.Index("ix_projections_event_household_date", "household_id", "event_date"),
        sa.Index(
            "ix_projections_event_run_account",
            "run_id",
            "account_id",
            "event_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"ProjectedEvent(id={self.id}, type={self.event_type!r}, "
            f"date={self.event_date}, amount={self.amount} {self.currency})"
        )


class ProjectionBreachEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A projected breach of a financial limit or milestone.

    Produced alongside a ProjectionRun. One row per breach detected.
    """

    __tablename__ = "projections_breach_event"

    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("projections_run.id", ondelete="CASCADE"),
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
        comment="Raw UUID; no FK (cross-module boundary)",
    )
    breach_type: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        comment="negative_balance | credit_limit | goal_reached | debt_free",
    )
    breach_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.Index("ix_projections_breach_run", "run_id"),
        sa.Index("ix_projections_breach_household", "household_id"),
    )

    def __repr__(self) -> str:
        return (
            f"ProjectionBreachEvent(id={self.id}, type={self.breach_type!r}, "
            f"date={self.breach_date})"
        )
