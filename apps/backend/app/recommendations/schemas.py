"""Pydantic schemas for the recommendations domain API."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.recommendations.enums import RecommendationSource, RecommendationStatus


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    source: RecommendationSource
    target_subsystem: str
    target_entity_id: uuid.UUID | None
    proposed_value: dict[str, Any]
    rationale_text: str
    rationale_data: dict[str, Any]
    confidence: Decimal | None
    status: RecommendationStatus
    expires_at: datetime | None
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    auto_apply: bool
    created_at: datetime
    updated_at: datetime


class AutoApplyRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    source: RecommendationSource
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AutoApplyToggle(BaseModel):
    enabled: bool
