"""Pydantic schemas for the classification domain API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.classification.enums import IncomeSourceSubType, RuleMode, StrictnessMode, VariabilityModel
from app.platform.money import MoneyDecimal

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    color: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None
    color: str | None = None
    sort_order: int | None = None
    budget_role: str | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID | None
    name: str
    parent_id: uuid.UUID | None
    system: bool
    deletable: bool
    renameable: bool
    color: str | None
    sort_order: int
    budget_role: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------


class TagCreate(BaseModel):
    name: str
    color: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class CategoryReorderItem(BaseModel):
    category_id: uuid.UUID
    sort_order: int


class CategoryReorderRequest(BaseModel):
    items: list[CategoryReorderItem]


class TagReorderItem(BaseModel):
    tag_id: uuid.UUID
    sort_order: int


class TagReorderRequest(BaseModel):
    items: list[TagReorderItem]


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    color: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class RuleConditionSchema(BaseModel):
    field: Literal[
        "merchant_name",
        "description",
        "amount",
        "account",
        "direction",
        "transaction_type",
    ]
    operator: Literal[
        "equals",
        "contains",
        "starts_with",
        "pattern_match",
        "amount_equals",
        "amount_between",
    ]
    value: str | None = None
    min: str | None = None
    max: str | None = None


class RuleActionSchema(BaseModel):
    type: Literal["set_category", "add_tag", "set_merchant_name", "set_transaction_type"]
    category_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None
    value: str | None = None


class RuleCreate(BaseModel):
    name: str
    priority: int
    conditions: list[RuleConditionSchema]
    actions: list[RuleActionSchema]
    mode: RuleMode = RuleMode.AUTO_APPLY
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    priority: int | None = None
    conditions: list[RuleConditionSchema] | None = None
    actions: list[RuleActionSchema] | None = None
    mode: RuleMode | None = None
    enabled: bool | None = None


class RulePriorityItem(BaseModel):
    rule_id: uuid.UUID
    priority: int


class RulePriorityReorderRequest(BaseModel):
    items: list[RulePriorityItem]


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    priority: int
    conditions: list[Any]
    actions: list[Any]
    mode: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TransactionSummary(BaseModel):
    id: uuid.UUID
    posted_date: date
    description: str
    merchant_name: str | None
    amount: Decimal
    currency: str
    direction: str


class RuleTestResult(BaseModel):
    matching_transaction_ids: list[uuid.UUID]
    match_count: int
    sample_count: int
    sample_transactions: list[TransactionSummary] = []


# ---------------------------------------------------------------------------
# IncomeSource
# ---------------------------------------------------------------------------


class DepositSplitEntry(BaseModel):
    account_id: uuid.UUID
    amount_or_percentage: MoneyDecimal


class IncomeSourceCreate(BaseModel):
    attributed_to_user_id: uuid.UUID
    employer_name: str
    sub_type: IncomeSourceSubType
    expected_cadence: str | None = None
    expected_amount_min: MoneyDecimal
    expected_amount_max: MoneyDecimal
    currency: str = "USD"
    account_id: uuid.UUID | None = None
    variability_model: VariabilityModel = VariabilityModel.FIXED
    deposit_split_pattern: list[DepositSplitEntry] = []


class IncomeSourceUpdate(BaseModel):
    employer_name: str | None = None
    sub_type: IncomeSourceSubType | None = None
    expected_cadence: str | None = None
    expected_amount_min: MoneyDecimal | None = None
    expected_amount_max: MoneyDecimal | None = None
    currency: str | None = None
    account_id: uuid.UUID | None = None
    variability_model: VariabilityModel | None = None
    deposit_split_pattern: list[DepositSplitEntry] | None = None


class IncomeSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    attributed_to_user_id: uuid.UUID
    employer_name: str
    sub_type: str
    expected_cadence: str | None
    expected_amount_min: Decimal
    expected_amount_max: Decimal
    currency: str
    account_id: uuid.UUID | None
    variability_model: str
    deposit_split_pattern: list[Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Household settings
# ---------------------------------------------------------------------------


class HouseholdSettingsUpdate(BaseModel):
    strictness: StrictnessMode


class HouseholdSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    household_id: uuid.UUID
    strictness: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Classification results
# ---------------------------------------------------------------------------


class ClassificationResultOut(BaseModel):
    allocation_updates: int
    suggestions: int
    hitl_items: int


class ReclassifyAllOut(BaseModel):
    job_id: str
