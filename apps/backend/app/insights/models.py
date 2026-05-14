"""SQLAlchemy models for the insights module.

Tables:
  insights_provider_config  -- per-household AI provider configuration
  insights_token_budget     -- per-period token and cost limits + usage
  insights_audit_log        -- append-only record of every LLM call
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.time import utcnow


class InsightProviderConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """AI provider configuration for a household.

    credentials_encrypted stores a Fernet token (from security.encryption.encrypt_dict)
    containing {"api_key": "<key>"}. Never log or expose this field.
    """

    __tablename__ = "insights_provider_config"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="local_ollama | local_llamacpp | anthropic | openai | disabled",
    )
    priority: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        comment="lower number = higher priority in provider fallback chain",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    base_url: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="required for local providers; null for remote",
    )
    model_name: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    credentials_encrypted: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Fernet token containing API key — never stored plaintext",
    )
    ai_data_sharing: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="generalizations_only",
        server_default=sa.text("'generalizations_only'"),
        comment="disabled | generalizations_only | aggregates_only | redacted | full",
    )

    __table_args__ = (
        sa.Index("ix_insights_provider_config_household", "household_id"),
        sa.Index(
            "ix_insights_provider_config_household_priority",
            "household_id",
            "priority",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"InsightProviderConfig(id={self.id}, provider={self.provider!r}, "
            f"priority={self.priority}, enabled={self.enabled})"
        )


class TokenBudget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-period token and cost budget for a household.

    One row per household per calendar month (period_start = first day of month).
    Created on first use within a period. Limits are configured via PATCH /budget.
    Usage counters (tokens_used, cost_used) are incremented after each LLM call.
    """

    __tablename__ = "insights_token_budget"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="first day of the billing month",
    )
    token_limit: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="monthly token cap; null = no limit",
    )
    cost_limit: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(precision=10, scale=4, asdecimal=True),
        nullable=True,
        comment="monthly cost cap; null = no limit",
    )
    currency: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        default="USD",
        server_default=sa.text("'USD'"),
    )
    tokens_used: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    cost_used: Mapped[Decimal] = mapped_column(
        sa.Numeric(precision=10, scale=4, asdecimal=True),
        nullable=False,
        default=Decimal("0"),
        server_default=sa.text("0"),
    )
    overage_behavior: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        default="block",
        server_default=sa.text("'block'"),
        comment="block | warn_and_continue | silent",
    )

    __table_args__ = (
        sa.Index("ix_insights_token_budget_household", "household_id"),
        sa.UniqueConstraint(
            "household_id",
            "period_start",
            name="uq_insights_token_budget_household_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"TokenBudget(id={self.id}, household_id={self.household_id}, "
            f"period_start={self.period_start}, tokens_used={self.tokens_used})"
        )


class InsightAuditLog(Base, UUIDPrimaryKeyMixin):
    """Append-only audit trail of every LLM call — success or failure.

    Written unconditionally by service.complete(). DB role has INSERT-only access.
    Never updated or deleted.
    """

    __tablename__ = "insights_audit_log"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    prompt_template: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="template string, not the rendered prompt — avoids storing PII",
    )
    prompt_fingerprint: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="SHA-256 of the rendered (post-redaction) prompt",
    )
    response_fingerprint: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="SHA-256 of the response; null on failure",
    )
    tokens_used: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    cost: Mapped[Decimal] = mapped_column(
        sa.Numeric(precision=10, scale=4, asdecimal=True),
        nullable=False,
        default=Decimal("0"),
    )
    currency: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        default="USD",
    )
    insight_category: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="anomaly | pattern | rationale | qa | categorization | forecast",
    )
    duration_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_insights_audit_log_household", "household_id"),
        sa.Index(
            "ix_insights_audit_log_household_created",
            "household_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"InsightAuditLog(id={self.id}, provider={self.provider!r}, "
            f"category={self.insight_category!r}, success={self.success})"
        )
