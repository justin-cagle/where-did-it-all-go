"""Pydantic schemas for the projections domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.platform.money import MoneyDecimal
from app.projections.enums import (
    BreachType,
    OverrideType,
    ProjectedConfidence,
    ProjectedDirection,
    ProjectedEventType,
    ProjectionRunStatus,
)

# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


class ScenarioOverride(BaseModel):
    """One delta applied on top of base projection inputs."""

    type: OverrideType
    recurrence_id: uuid.UUID | None = None
    budget_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    amount: MoneyDecimal | None = None
    currency: str | None = None
    cadence: str | None = None
    start_date: date | None = None
    extra_payment: MoneyDecimal | None = None
    monthly_amount: MoneyDecimal | None = None
    balance: MoneyDecimal | None = None
    extra: dict[str, Any] = {}


class ScenarioCreate(BaseModel):
    name: str | None = None
    overrides: list[ScenarioOverride] = []
    saved: bool = False


class ScenarioUpdate(BaseModel):
    name: str | None = None
    saved: bool | None = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str | None
    overrides: list[Any]
    base_run_id: uuid.UUID | None
    saved: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Projection run
# ---------------------------------------------------------------------------


class ProjectionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    scenario_id: uuid.UUID | None
    as_of_date: date
    horizon_months: int
    inputs_hash: str
    computed_at: datetime
    expires_at: datetime
    status: ProjectionRunStatus


class RunProjectionRequest(BaseModel):
    horizon_months: int = 12
    as_of: date | None = None
    force: bool = False


# ---------------------------------------------------------------------------
# Projected event
# ---------------------------------------------------------------------------


class ProjectedEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    run_id: uuid.UUID
    scenario_id: uuid.UUID | None
    account_id: uuid.UUID
    event_date: date
    event_type: ProjectedEventType
    amount: Decimal
    currency: str
    direction: ProjectedDirection
    confidence: ProjectedConfidence
    source_id: uuid.UUID | None
    source_type: str | None
    description: str | None
    metadata_: dict[str, Any]


# ---------------------------------------------------------------------------
# Breach event
# ---------------------------------------------------------------------------


class ProjectionBreachEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    breach_type: BreachType
    breach_date: date
    amount: Decimal
    currency: str
    description: str | None


# ---------------------------------------------------------------------------
# Aggregated views
# ---------------------------------------------------------------------------


class BalancePoint(BaseModel):
    event_date: date
    account_id: uuid.UUID
    balance: Decimal
    currency: str


class CashflowPeriod(BaseModel):
    period_start: date
    period_end: date
    total_income: Decimal
    total_expenses: Decimal
    net_cashflow: Decimal
    currency: str


class NetWorthPoint(BaseModel):
    event_date: date
    net_worth: Decimal
    currency: str


# ---------------------------------------------------------------------------
# Projection response (run + summary)
# ---------------------------------------------------------------------------


class ProjectionResponse(BaseModel):
    run: ProjectionRunOut
    events_count: int
    breaches_count: int
