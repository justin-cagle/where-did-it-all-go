"""Pydantic v2 request/response schemas for the transactions module."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.platform.money import MoneyDecimal
from app.transactions.enums import (
    DedupResolution,
    GroupType,
    TransactionDirection,
    TransactionState,
    TransactionType,
)


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class TransactionCreate(BaseModel):
    """Create a transaction via manual entry (no ingest wiring)."""

    amount: MoneyDecimal
    currency: str = Field(default="USD", min_length=3, max_length=3)
    direction: TransactionDirection
    transaction_type: TransactionType | None = None
    state: TransactionState = TransactionState.PENDING
    posted_date: date
    pending_date: date | None = None
    occurred_at: date
    description: str = Field(min_length=1)
    merchant_name: str | None = None
    external_id: str | None = None
    manually_categorized: bool = False

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal(0):
            raise ValueError("amount must be positive")
        return v


class TransactionStateUpdate(BaseModel):
    """Transition the transaction state."""

    state: TransactionState


class TransactionOut(_Base):
    """Transaction info returned in list and detail responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    currency: str
    direction: str
    transaction_type: str | None
    state: str
    posted_date: date
    pending_date: date | None
    occurred_at: date
    description: str
    merchant_name: str | None
    external_id: str | None
    recurrence_id: uuid.UUID | None
    manually_categorized: bool
    transfer_peer_id: uuid.UUID | None
    refund_peer_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TransactionDetailOut(TransactionOut):
    """Transaction detail — includes split allocations."""

    splits: list["SplitAllocationOut"] = []


# ---------------------------------------------------------------------------
# SplitAllocation
# ---------------------------------------------------------------------------


class SplitAllocationIn(BaseModel):
    """One slice in a set-splits request."""

    amount: MoneyDecimal
    currency: str = Field(default="USD", min_length=3, max_length=3)
    category_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = []
    attributed_to_user_id: uuid.UUID | None = None
    manually_categorized: bool = False

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal(0):
            raise ValueError("split amount must be positive")
        return v


class SplitsSetRequest(BaseModel):
    """Replace all splits on a transaction."""

    splits: list[SplitAllocationIn] = Field(min_length=1)


class SplitAllocationOut(_Base):
    """Split allocation info returned in responses."""

    id: uuid.UUID
    transaction_id: uuid.UUID
    household_id: uuid.UUID
    amount: Decimal
    currency: str
    category_id: uuid.UUID | None
    tag_ids: list[Any]
    attributed_to_user_id: uuid.UUID | None
    manually_categorized: bool
    rule_id: uuid.UUID | None
    rule_fired_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Transfer and Refund pairing
# ---------------------------------------------------------------------------


class TransferPairRequest(BaseModel):
    """Link two transactions as an internal or external transfer."""

    peer_id: uuid.UUID
    transfer_type: Literal["internal", "external"]


class RefundPairRequest(BaseModel):
    """Link this transaction to its refund counterpart."""

    peer_id: uuid.UUID


class RefundCandidateOut(BaseModel):
    """A candidate credit transaction that could be a refund."""

    transaction: TransactionOut
    days_apart: int


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class DeduplicationLogOut(_Base):
    """Dedup candidate pair returned in responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    candidate_a_id: uuid.UUID
    candidate_b_id: uuid.UUID
    confidence: Decimal
    match_reason: str
    resolution: str
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DedupResolveRequest(BaseModel):
    """Resolve a pending dedup candidate as merged or rejected."""

    resolution: Literal[DedupResolution.MERGED, DedupResolution.REJECTED]


# ---------------------------------------------------------------------------
# PaymentGroup
# ---------------------------------------------------------------------------


class PaymentGroupCreate(BaseModel):
    """Create a payment group from confirmed candidate transactions."""

    group_type: GroupType
    member_transaction_ids: list[uuid.UUID] = Field(min_length=2)


class PaymentGroupOut(_Base):
    """Payment group info returned in responses."""

    id: uuid.UUID
    household_id: uuid.UUID
    group_type: str
    member_transaction_ids: list[Any]
    created_at: datetime
    updated_at: datetime
