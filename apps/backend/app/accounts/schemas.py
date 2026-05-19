"""Pydantic v2 request/response schemas for the accounts module."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.accounts.enums import AccountType, MinimumPaymentStrategy
from app.platform.money import MoneyDecimal


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


class AccountCreate(BaseModel):
    """Create a new account."""

    name: str = Field(min_length=1, max_length=255)
    institution: str | None = Field(default=None, max_length=255)
    account_type: AccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_balance: MoneyDecimal = Field(default=Decimal("0"))

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class AccountUpdate(BaseModel):
    """Mutable account fields."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    current_balance: MoneyDecimal | None = None
    allow_negative_balance: bool = False


class AccountOut(_Base):
    """Account info returned in responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    institution: str | None
    account_type: str
    currency: str
    current_balance: Decimal
    is_manual: bool
    account_group_id: uuid.UUID | None
    authoritative_sync_config_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# AccountGroup
# ---------------------------------------------------------------------------


class AccountGroupCreate(BaseModel):
    """Create an account group, optionally with initial members."""

    name: str = Field(min_length=1, max_length=255)
    primary_holder_id: uuid.UUID | None = None
    authorized_user_ids: list[uuid.UUID] = []
    member_account_ids: list[uuid.UUID] = []


class AccountGroupUpdate(BaseModel):
    """Mutable account group fields."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    primary_holder_id: uuid.UUID | None = None
    authorized_user_ids: list[uuid.UUID] | None = None


class AccountGroupOut(_Base):
    """Account group info returned in responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    primary_holder_id: uuid.UUID | None
    authorized_user_ids: list[Any]
    created_at: datetime


class GroupCandidateOut(BaseModel):
    """Candidate account pair surfaced for HITL grouping review."""

    account_a_id: uuid.UUID
    account_b_id: uuid.UUID
    reason: str
    similarity_score: float


# ---------------------------------------------------------------------------
# DebtAccount
# ---------------------------------------------------------------------------


class DebtAnnotationCreate(BaseModel):
    """Annotate a debt account with payment strategy and initial APR tranche."""

    minimum_payment_strategy: MinimumPaymentStrategy = MinimumPaymentStrategy.FROM_STATEMENT
    statement_day: int | None = Field(default=None, ge=1, le=28)
    due_day: int | None = Field(default=None, ge=1, le=28)
    payoff_target_date: date | None = None
    initial_balance: MoneyDecimal
    initial_apr: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    term: int | None = Field(default=None, gt=0)
    promotional_period_end: date | None = None
    effective_from: date

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class DebtAnnotationUpdate(BaseModel):
    """Mutable debt annotation fields."""

    minimum_payment_strategy: MinimumPaymentStrategy | None = None
    statement_day: int | None = Field(default=None, ge=1, le=28)
    due_day: int | None = Field(default=None, ge=1, le=28)
    payoff_target_date: date | None = None


class DebtAnnotationOut(_Base):
    """Debt annotation info returned in responses."""

    id: uuid.UUID
    account_id: uuid.UUID
    minimum_payment_strategy: str
    statement_day: int | None
    due_day: int | None
    payoff_target_date: date | None
    created_at: datetime


class DebtBalanceCreate(BaseModel):
    """Add a new APR tranche, closing the current one."""

    principal_balance: MoneyDecimal
    currency: str = Field(default="USD", min_length=3, max_length=3)
    apr: Decimal = Field(gt=Decimal("0"))
    term: int | None = Field(default=None, gt=0)
    promotional_period_end: date | None = None
    effective_from: date

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class DebtBalanceOut(_Base):
    """Debt balance (APR tranche) info returned in responses."""

    id: uuid.UUID
    debt_account_id: uuid.UUID
    principal_balance: Decimal
    currency: str
    apr: Decimal
    term: int | None
    promotional_period_end: date | None
    effective_from: date
    effective_to: date | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Balance history
# ---------------------------------------------------------------------------


class BalanceHistoryPoint(BaseModel):
    """One balance reading per day, derived from audit log reconciliation entries."""

    date: date
    balance: Decimal
