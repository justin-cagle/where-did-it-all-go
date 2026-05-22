"""Pydantic schemas for the insights module API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------


class ProviderConfigCreate(BaseModel):
    provider: str = Field(
        ...,
        pattern="^(local_ollama|local_llamacpp|anthropic|openai|disabled)$",
    )
    priority: int = Field(default=0, ge=0)
    enabled: bool = True
    base_url: str | None = None
    model_name: str | None = None
    credentials: dict[str, Any] | None = None
    ai_data_sharing: str = Field(
        default="generalizations_only",
        pattern="^(disabled|generalizations_only|aggregates_only|redacted|full)$",
    )


class ProviderConfigUpdate(BaseModel):
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0)
    base_url: str | None = None
    model_name: str | None = None
    credentials: dict[str, Any] | None = None
    ai_data_sharing: str | None = Field(
        default=None,
        pattern="^(disabled|generalizations_only|aggregates_only|redacted|full)$",
    )


class ProviderConfigOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    provider: str
    priority: int
    enabled: bool
    base_url: str | None
    model_name: str | None
    ai_data_sharing: str
    created_at: datetime
    updated_at: datetime
    # credentials_encrypted intentionally excluded from responses

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


class TokenBudgetOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    period_start: date
    token_limit: int | None
    cost_limit: Decimal | None
    currency: str
    tokens_used: int
    cost_used: Decimal
    overage_behavior: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenBudgetUpdate(BaseModel):
    token_limit: int | None = Field(default=None, ge=0)
    cost_limit: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    overage_behavior: str | None = Field(
        default=None,
        pattern="^(block|warn_and_continue|silent)$",
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLogOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    provider: str
    model_name: str
    prompt_template: str
    prompt_fingerprint: str
    response_fingerprint: str | None
    tokens_used: int
    cost: Decimal
    currency: str
    insight_category: str
    duration_ms: int
    success: bool
    error_detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Q&A endpoint
# ---------------------------------------------------------------------------


class ConversationTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: list[ConversationTurn] = Field(default_factory=lambda: [], max_length=20)


class AskResponse(BaseModel):
    answer: str | None
    provider_used: str | None
    reason: str | None = Field(
        default=None,
        description="no_provider | budget_exceeded | disabled (present when answer is null)",
    )


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------


class GenerateResponse(BaseModel):
    job_id: str
    status: str = "enqueued"


# ---------------------------------------------------------------------------
# Ollama model management
# ---------------------------------------------------------------------------


class OllamaModelOut(BaseModel):
    name: str
    size_bytes: int
    modified_at: str


class OllamaModelsResponse(BaseModel):
    models: list[OllamaModelOut]


class OllamaPullRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Provider availability test
# ---------------------------------------------------------------------------


class ProviderTestResponse(BaseModel):
    available: bool
    model_name: str | None
    error: str | None
