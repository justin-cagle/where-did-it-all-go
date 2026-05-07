"""Pydantic schemas for the goals domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.goals.enums import (
    BurnUpStatus,
    CompletionPolicy,
    ContributionType,
    FundingSourceType,
    FundingStrategy,
    GoalStatus,
    GoalType,
)
from app.platform.money import MoneyDecimal

# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------


class GoalCreate(BaseModel):
    name: str
    description: str | None = None
    goal_type: GoalType
    target_amount: MoneyDecimal | None = None
    currency: str = "USD"
    target_date: date | None = None
    funding_strategy: FundingStrategy = FundingStrategy.VIRTUAL_ALLOCATION
    completion_policy: CompletionPolicy = CompletionPolicy.PROMPT_ON_COMPLETE
    auto_extend_amount: MoneyDecimal | None = None
    owner_id: uuid.UUID | None = None
    linked_debt_plan_id: uuid.UUID | None = None
    linked_category_id: uuid.UUID | None = None
    minimum_balance_threshold: MoneyDecimal | None = None
    metadata_: dict[str, Any] = {}


class GoalUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_amount: MoneyDecimal | None = None
    currency: str | None = None
    target_date: date | None = None
    funding_strategy: FundingStrategy | None = None
    completion_policy: CompletionPolicy | None = None
    auto_extend_amount: MoneyDecimal | None = None
    owner_id: uuid.UUID | None = None
    linked_debt_plan_id: uuid.UUID | None = None
    linked_category_id: uuid.UUID | None = None
    minimum_balance_threshold: MoneyDecimal | None = None
    metadata_: dict[str, Any] | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    description: str | None
    goal_type: GoalType
    status: GoalStatus
    target_amount: Decimal | None
    currency: str
    target_date: date | None
    funding_strategy: FundingStrategy
    completion_policy: CompletionPolicy
    auto_extend_amount: Decimal | None
    owner_id: uuid.UUID | None
    linked_debt_plan_id: uuid.UUID | None
    linked_category_id: uuid.UUID | None
    minimum_balance_threshold: Decimal | None
    metadata_: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# GoalFundingSource
# ---------------------------------------------------------------------------


class FundingSourceCreate(BaseModel):
    source_type: FundingSourceType
    source_id: uuid.UUID | None = None
    attributed_to_user_id: uuid.UUID | None = None


class FundingSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    household_id: uuid.UUID
    source_type: FundingSourceType
    source_id: uuid.UUID | None
    attributed_to_user_id: uuid.UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# GoalContribution
# ---------------------------------------------------------------------------


class ContributionCreate(BaseModel):
    amount: MoneyDecimal
    currency: str = "USD"
    contributed_at: date
    contribution_type: ContributionType = ContributionType.MANUAL
    transaction_id: uuid.UUID | None = None
    attributed_to_user_id: uuid.UUID | None = None
    note: str | None = None


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    household_id: uuid.UUID
    amount: Decimal
    currency: str
    contributed_at: date
    contribution_type: ContributionType
    transaction_id: uuid.UUID | None
    attributed_to_user_id: uuid.UUID | None
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# GoalSnapshot (burn-up)
# ---------------------------------------------------------------------------


class GoalSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    snapshot_date: date
    cumulative_actual: Decimal
    currency: str
    cumulative_expected: Decimal
    required_pace: Decimal
    actual_pace: Decimal
    projected_completion_date: date | None
    gap_to_close: Decimal
    progress_pct: Decimal
    burn_up_status: BurnUpStatus
    computed_at: datetime


# ---------------------------------------------------------------------------
# Per-user contribution breakdown
# ---------------------------------------------------------------------------


class UserContributionTotal(BaseModel):
    attributed_to_user_id: uuid.UUID | None
    total: Decimal
    currency: str


class ContributionBreakdown(BaseModel):
    contributions: list[ContributionOut]
    per_user: list[UserContributionTotal]
    household_total: Decimal
    currency: str
