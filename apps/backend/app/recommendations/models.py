"""SQLAlchemy models for the recommendations domain.

Tables:
  recommendations_recommendation   -- cross-module intent and resolution tracker
  recommendations_auto_apply_rule  -- per-source auto-apply preference per household
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Recommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Cross-module suggestion awaiting user resolution.

    Never applies changes itself — records intent and resolution only.
    The calling subsystem reads the accepted Recommendation and performs the
    actual mutation in its own tables.
    """

    __tablename__ = "recommendations_recommendation"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment=(
            "debt_engine | goal_engine | recurrence_detector | refund_pairing | "
            "transfer_detection | ai_insights | classification_pipeline | ingest"
        ),
    )
    target_subsystem: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="e.g. 'budgets', 'transactions', 'recurrences'",
    )
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Entity being acted on; raw UUID, no FK across module boundary",
    )
    proposed_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Structured proposed change — schema is source-specific",
    )
    rationale_text: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Human-readable explanation carried forward to audit log on accept",
    )
    rationale_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Structured metadata for programmatic use by the calling subsystem",
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(5, 4),
        nullable=True,
        comment="Subsystem confidence 0.0000-1.0000; NULL when not applicable",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="pending",
        comment="pending | accepted | rejected | expired",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="If set, expire_stale() transitions to expired after this time",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="User who resolved this; raw UUID, no FK across module boundary",
    )
    auto_apply: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        comment="True when accepted via auto-apply; False for explicit HITL",
    )

    __table_args__ = (
        sa.Index("ix_recommendations_recommendation_household", "household_id"),
        sa.Index(
            "ix_recommendations_recommendation_pending",
            "household_id",
            postgresql_where=sa.text("status = 'pending'"),
        ),
        sa.Index("ix_recommendations_recommendation_source", "source"),
    )

    def __repr__(self) -> str:
        return (
            f"Recommendation(id={self.id}, source={self.source!r}, "
            f"status={self.status!r}, target={self.target_subsystem!r})"
        )


class AutoApplyRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-source auto-apply preference for a household.

    When enabled, should_auto_apply() returns True for this source.
    Opt-in and per-source only — no global auto-apply switch.
    Advisory: callers must still call accept() explicitly.
    """

    __tablename__ = "recommendations_auto_apply_rule"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="Same enum values as Recommendation.source",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )

    __table_args__ = (
        sa.Index("ix_recommendations_auto_apply_rule_household", "household_id"),
        sa.UniqueConstraint(
            "household_id",
            "source",
            name="uq_recommendations_auto_apply_rule_household_source",
        ),
    )

    def __repr__(self) -> str:
        return f"AutoApplyRule(id={self.id}, source={self.source!r}, enabled={self.enabled})"
