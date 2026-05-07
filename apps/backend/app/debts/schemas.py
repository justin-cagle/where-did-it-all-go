"""Pydantic schemas for the debts domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.debts.enums import DebtPlanMethod
from app.platform.money import MoneyDecimal

# ---------------------------------------------------------------------------
# DebtPlan
# ---------------------------------------------------------------------------


class DebtPlanCreate(BaseModel):
    name: str
    method: DebtPlanMethod
    monthly_extra_payment: MoneyDecimal = Decimal("0")
    currency: str = "USD"
    snowball_flow: bool = True
    account_ids: list[uuid.UUID] = []
    effective_from: date | None = None


class DebtPlanUpdate(BaseModel):
    name: str | None = None
    method: DebtPlanMethod | None = None
    monthly_extra_payment: MoneyDecimal | None = None
    currency: str | None = None
    snowball_flow: bool | None = None
    account_ids: list[uuid.UUID] | None = None
    effective_from: date | None = None


class DebtPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_group_id: uuid.UUID
    household_id: uuid.UUID
    name: str
    method: DebtPlanMethod
    monthly_extra_payment: Decimal
    currency: str
    snowball_flow: bool
    account_ids: list[Any]
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# DebtPlanSchedule
# ---------------------------------------------------------------------------


class DebtPlanScheduleRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    account_id: uuid.UUID
    period_date: date
    opening_balance: Decimal
    currency: str
    payment: Decimal
    principal: Decimal
    interest: Decimal
    closing_balance: Decimal
    is_payoff: bool


class DebtPlanScheduleByAccount(BaseModel):
    account_id: uuid.UUID
    rows: list[DebtPlanScheduleRow]


# ---------------------------------------------------------------------------
# DebtPlanSummary
# ---------------------------------------------------------------------------


class DebtPlanSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    total_interest: Decimal
    currency: str
    total_paid: Decimal
    months_to_payoff: int
    interest_savings_vs_minimums: Decimal
    payoff_date: date | None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class DebtPlanComparisonItem(BaseModel):
    label: str
    total_interest: Decimal
    total_paid: Decimal
    months_to_payoff: int
    payoff_date: date | None
    interest_savings_vs_minimums: Decimal


class DebtPlanComparisonOut(BaseModel):
    current: DebtPlanComparisonItem
    compared: DebtPlanComparisonItem


# ---------------------------------------------------------------------------
# Payment recording
# ---------------------------------------------------------------------------


class DebtPaymentRecord(BaseModel):
    amount: MoneyDecimal
    currency: str = "USD"
    payment_date: date | None = None
