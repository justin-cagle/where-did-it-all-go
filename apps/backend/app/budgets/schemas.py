"""Pydantic schemas for the budgets domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.budgets.enums import (
    BudgetLineStatus,
    BudgetMethod,
    BudgetPeriod,
    ExpectedIncomeStrategy,
    RolloverPolicy,
)
from app.platform.money import MoneyDecimal

# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class BudgetCreate(BaseModel):
    name: str
    period: BudgetPeriod
    start_date: date
    end_date: date | None = None
    owner_id: uuid.UUID | None = None
    method: BudgetMethod
    expected_income_strategy: ExpectedIncomeStrategy = ExpectedIncomeStrategy.FIXED
    expected_income: MoneyDecimal | None = None
    currency: str = "USD"
    income_rolling_periods: int = 3
    scope_accounts: list[uuid.UUID] = []
    scope_categories: list[uuid.UUID] = []
    scope_tags: list[uuid.UUID] = []
    pay_period_income_source_id: uuid.UUID | None = None


class BudgetUpdate(BaseModel):
    name: str | None = None
    end_date: date | None = None
    method: BudgetMethod | None = None
    expected_income_strategy: ExpectedIncomeStrategy | None = None
    expected_income: MoneyDecimal | None = None
    currency: str | None = None
    income_rolling_periods: int | None = None
    scope_accounts: list[uuid.UUID] | None = None
    scope_categories: list[uuid.UUID] | None = None
    scope_tags: list[uuid.UUID] | None = None
    pay_period_income_source_id: uuid.UUID | None = None
    effective_from: date | None = None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    budget_group_id: uuid.UUID
    household_id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    period: BudgetPeriod
    start_date: date
    end_date: date | None
    method: BudgetMethod
    expected_income_strategy: ExpectedIncomeStrategy
    expected_income: Decimal | None
    currency: str
    income_rolling_periods: int
    scope_accounts: list[Any]
    scope_categories: list[Any]
    scope_tags: list[Any]
    pay_period_income_source_id: uuid.UUID | None
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# BudgetLine
# ---------------------------------------------------------------------------


class BudgetLineCreate(BaseModel):
    category_id: uuid.UUID
    tag_id: uuid.UUID | None = None
    planned_amount: MoneyDecimal
    currency: str = "USD"
    rollover_policy: RolloverPolicy = RolloverPolicy.NONE
    rollover_cap: MoneyDecimal | None = None


class BudgetLineUpdate(BaseModel):
    planned_amount: MoneyDecimal | None = None
    currency: str | None = None
    rollover_policy: RolloverPolicy | None = None
    rollover_cap: MoneyDecimal | None = None


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    budget_id: uuid.UUID
    household_id: uuid.UUID
    category_id: uuid.UUID
    tag_id: uuid.UUID | None
    planned_amount: Decimal
    currency: str
    rollover_policy: RolloverPolicy
    rollover_cap: Decimal | None
    carried_amount: Decimal
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# BudgetPeriodActual
# ---------------------------------------------------------------------------


class BudgetPeriodActualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    budget_id: uuid.UUID
    budget_line_id: uuid.UUID
    period_start: date
    period_end: date
    planned_amount: Decimal
    currency: str
    actual_amount: Decimal
    carried_in: Decimal
    carried_out: Decimal


# ---------------------------------------------------------------------------
# Budget status
# ---------------------------------------------------------------------------


class BudgetLineStatusOut(BaseModel):
    line: BudgetLineOut
    period_actual: BudgetPeriodActualOut | None
    planned: Decimal
    actual: Decimal
    carried_in: Decimal
    remaining: Decimal
    status: BudgetLineStatus


class BudgetStatusOut(BaseModel):
    budget: BudgetOut
    period_start: date
    period_end: date
    expected_income: Decimal | None
    lines: list[BudgetLineStatusOut]


# ---------------------------------------------------------------------------
# Period income override
# ---------------------------------------------------------------------------


class PeriodIncomeSet(BaseModel):
    period_start: date
    expected_income: MoneyDecimal
    currency: str = "USD"


class PeriodIncomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    budget_group_id: uuid.UUID
    period_start: date
    expected_income: Decimal
    currency: str
