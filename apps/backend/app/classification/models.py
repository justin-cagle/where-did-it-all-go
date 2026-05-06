"""SQLAlchemy models for the classification domain.

Tables:
  classification_category              -- 2-level category hierarchy
                                        (global system + household-scoped)
  classification_tag                   -- flat tags, household-scoped
  classification_rule                  -- user-defined rules with conditions/actions
  classification_income_source         -- known income streams, household-scoped
  classification_household_settings    -- per-household pipeline configuration (strictness, etc.)
"""

import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.money import CURRENCY_TYPE, MONEY_TYPE


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A category in the 2-level hierarchy.

    household_id is NULL for system categories (Transfer, Uncategorized, Income, Refund)
    which are global and shared across all households. All other categories are
    household-scoped. Children of system categories are not permitted.
    """

    __tablename__ = "classification_category"

    household_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL for system categories shared across all households",
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("classification_category.id", ondelete="SET NULL"),
        nullable=True,
    )
    system: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    deletable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    renameable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    color: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    __table_args__ = (
        sa.Index("ix_classification_category_household", "household_id"),
        sa.Index("ix_classification_category_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"Category(id={self.id}, name={self.name!r}, system={self.system})"


class Tag(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A flat tag, household-scoped. Orthogonal to categories."""

    __tablename__ = "classification_tag"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    color: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (sa.Index("ix_classification_tag_household", "household_id"),)

    def __repr__(self) -> str:
        return f"Tag(id={self.id}, name={self.name!r})"


class Rule(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A user-defined classification rule: IF (conditions) THEN (actions).

    conditions: list of condition objects (field, operator, value)
    actions: list of action objects (type, category_id or tag_id)
    Priority ties broken by created_at (older rule wins).
    """

    __tablename__ = "classification_rule"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    priority: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    conditions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    mode: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="auto_apply",
        comment="auto_apply | suggest",
    )
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        sa.Index("ix_classification_rule_household", "household_id"),
        sa.Index(
            "ix_classification_rule_priority_order",
            "household_id",
            "priority",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"Rule(id={self.id}, name={self.name!r}, priority={self.priority})"


class IncomeSource(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A known income stream for a household member.

    Used in step 2 of the classification pipeline to lock payroll-type
    transactions to the Income category, bypassing user rules.
    """

    __tablename__ = "classification_income_source"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    attributed_to_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    employer_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sub_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        comment="payroll | bonus | rsu | reimbursement",
    )
    expected_cadence: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    expected_amount_min: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    expected_amount_max: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Raw UUID — no FK to accounts module (cross-module boundary)",
    )
    variability_model: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="fixed",
        comment="fixed | range | historical_distribution",
    )
    deposit_split_pattern: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="[{account_id, amount_or_percentage}] for split-deposit detection",
    )

    __table_args__ = (sa.Index("ix_classification_income_source_household", "household_id"),)

    def __repr__(self) -> str:
        return f"IncomeSource(id={self.id}, employer={self.employer_name!r})"


class HouseholdClassificationSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-household classification configuration.

    No soft delete — settings rows persist for the household lifetime.
    Created by seed_default_categories on household creation.
    """

    __tablename__ = "classification_household_settings"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    strictness: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="strict",
        comment="strict | best_guess | silent",
    )

    __table_args__ = (sa.Index("ix_classification_household_settings_household", "household_id"),)

    def __repr__(self) -> str:
        return (
            f"HouseholdClassificationSettings("
            f"household={self.household_id}, strictness={self.strictness!r})"
        )
