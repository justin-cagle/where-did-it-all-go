"""Pydantic schemas for the recurrences domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.platform.money import MoneyDecimal
from app.recurrences.enums import (
    AmountStrategy,
    Cadence,
    CandidateStatus,
    ExceptionType,
    MatchStatus,
    RecurrenceKind,
)

# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------


class RecurrenceCreate(BaseModel):
    account_id: uuid.UUID
    cadence: Cadence
    expected_amount: MoneyDecimal
    currency: str = "USD"
    tolerance: MoneyDecimal = Decimal("0")
    expected_day_of_period: int | None = None
    expected_amount_strategy: AmountStrategy = AmountStrategy.FIXED
    linked_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    merchant_name: str | None = None
    recurrence_metadata: dict[str, Any] = {}


class RecurrenceUpdate(BaseModel):
    cadence: Cadence | None = None
    expected_amount: MoneyDecimal | None = None
    currency: str | None = None
    tolerance: MoneyDecimal | None = None
    expected_day_of_period: int | None = None
    expected_amount_strategy: AmountStrategy | None = None
    linked_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None
    end_date: date | None = None
    merchant_name: str | None = None
    recurrence_metadata: dict[str, Any] | None = None


class RecurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    kind: RecurrenceKind
    cadence: Cadence
    expected_amount: Decimal
    currency: str
    tolerance: Decimal
    expected_day_of_period: int | None
    expected_amount_strategy: AmountStrategy
    linked_category_id: uuid.UUID | None
    linked_account_id: uuid.UUID | None
    start_date: date
    end_date: date | None
    paused: bool
    merchant_name: str | None
    recurrence_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    recurrence_id: uuid.UUID | None
    account_id: uuid.UUID
    merchant_name: str
    cadence: Cadence
    expected_amount: Decimal
    currency: str
    sample_transaction_ids: list[str]
    occurrence_count: int
    status: CandidateStatus
    detected_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ExceptionCreate(BaseModel):
    exception_type: ExceptionType
    affected_period: date
    override_amount: MoneyDecimal | None = None
    override_date: date | None = None
    note: str | None = None


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recurrence_id: uuid.UUID
    exception_type: ExceptionType
    affected_period: date
    override_amount: Decimal | None
    override_date: date | None
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recurrence_id: uuid.UUID
    transaction_id: uuid.UUID | None
    matched_at: datetime
    deviation_amount: Decimal | None
    deviation_days: int | None
    status: MatchStatus
    expected_date: date | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Expected events
# ---------------------------------------------------------------------------


class ExpectedEventOut(BaseModel):
    recurrence_id: uuid.UUID
    account_id: uuid.UUID
    expected_date: date
    expected_amount: Decimal
    currency: str
    cadence: Cadence
    merchant_name: str | None
    exception_type: ExceptionType | None = None
    override_amount: Decimal | None = None
    override_date: date | None = None
