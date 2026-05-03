"""SQLAlchemy models for the accounts domain.

Tables:
  accounts_account_group  — logical grouping for multi-feed accounts
  accounts_account        — base financial account entity
  accounts_manual_account — annotation: account is manually maintained
  accounts_debt_account   — annotation: account has debt-specific fields
  accounts_debt_balance   — APR tranche with effective-dated history
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.accounts.enums import AccountType, MinimumPaymentStrategy
from app.database import Base
from app.platform.db import (
    EffectiveDatedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.platform.money import CURRENCY_TYPE, MONEY_TYPE

_APR_TYPE = sa.Numeric(precision=7, scale=6, asdecimal=True)


class AccountGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Logical grouping for a single underlying account with multiple feed entries."""

    __tablename__ = "accounts_account_group"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    primary_holder_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    authorized_user_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="JSON array of user UUIDs who are authorized users of the underlying account",
    )

    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="account_group",
        lazy="select",
    )

    __table_args__ = (sa.Index("ix_accounts_account_group_household", "household_id"),)

    def __repr__(self) -> str:
        return f"AccountGroup(id={self.id}, name={self.name!r})"


class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Financial account — base entity for all account types."""

    __tablename__ = "accounts_account"

    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_household.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    institution: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    account_type: Mapped[str] = mapped_column(
        sa.Enum(AccountType, name="account_type", native_enum=False, length=32),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    current_balance: Mapped[Decimal] = mapped_column(
        MONEY_TYPE,
        nullable=False,
        default=Decimal(0),
    )
    is_manual: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    account_group_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_account_group.id", ondelete="SET NULL"),
        nullable=True,
    )

    account_group: Mapped["AccountGroup | None"] = relationship(
        "AccountGroup",
        back_populates="accounts",
        lazy="select",
    )
    debt_account: Mapped["DebtAccount | None"] = relationship(
        "DebtAccount",
        back_populates="account",
        uselist=False,
        lazy="select",
    )
    manual_account: Mapped["ManualAccount | None"] = relationship(
        "ManualAccount",
        back_populates="account",
        uselist=False,
        lazy="select",
    )

    __table_args__ = (
        sa.Index("ix_accounts_account_household", "household_id"),
        sa.Index("ix_accounts_account_type", "account_type"),
        sa.Index("ix_accounts_account_group", "account_group_id"),
    )

    def __repr__(self) -> str:
        return f"Account(id={self.id}, name={self.name!r}, type={self.account_type!r})"


class ManualAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Annotation marking an account as manually maintained — no sync required."""

    __tablename__ = "accounts_manual_account"

    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_account.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="manual_account",
        lazy="select",
    )

    __table_args__ = (sa.Index("ix_accounts_manual_account_account", "account_id", unique=True),)

    def __repr__(self) -> str:
        return f"ManualAccount(id={self.id}, account_id={self.account_id})"


class DebtAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Annotation layer over Account adding debt-specific metadata."""

    __tablename__ = "accounts_debt_account"

    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_account.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    minimum_payment_strategy: Mapped[str] = mapped_column(
        sa.Enum(
            MinimumPaymentStrategy,
            name="minimum_payment_strategy",
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=MinimumPaymentStrategy.FROM_STATEMENT,
    )
    statement_day: Mapped[int | None] = mapped_column(
        sa.SmallInteger,
        nullable=True,
        comment="Day of month (1-28) when statement closes",
    )
    due_day: Mapped[int | None] = mapped_column(
        sa.SmallInteger,
        nullable=True,
        comment="Day of month (1-28) when payment is due",
    )
    payoff_target_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="debt_account",
        lazy="select",
    )
    balances: Mapped[list["DebtBalance"]] = relationship(
        "DebtBalance",
        back_populates="debt_account",
        lazy="select",
        order_by="DebtBalance.effective_from",
    )

    __table_args__ = (sa.Index("ix_accounts_debt_account_account", "account_id", unique=True),)

    def __repr__(self) -> str:
        return f"DebtAccount(id={self.id}, account_id={self.account_id})"


class DebtBalance(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, EffectiveDatedMixin):
    """One APR tranche for a DebtAccount. Effective-dated history for rate changes."""

    __tablename__ = "accounts_debt_balance"

    debt_account_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("accounts_debt_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    principal_balance: Mapped[Decimal] = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str] = mapped_column(CURRENCY_TYPE, nullable=False, default="USD")
    apr: Mapped[Decimal] = mapped_column(
        _APR_TYPE,
        nullable=False,
        comment="APR as decimal fraction: 0.2499 = 24.99%",
    )
    term: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Loan term in months",
    )
    promotional_period_end: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    debt_account: Mapped["DebtAccount"] = relationship(
        "DebtAccount",
        back_populates="balances",
        lazy="select",
    )

    __table_args__ = (
        sa.Index("ix_accounts_debt_balance_debt_account", "debt_account_id"),
        sa.Index(
            "ix_accounts_debt_balance_current",
            "debt_account_id",
            postgresql_where=sa.text("effective_to IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DebtBalance(id={self.id}, apr={self.apr}, " f"effective_from={self.effective_from})"
        )
