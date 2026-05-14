"""Enums for the insights module."""

from enum import StrEnum


class InsightProvider(StrEnum):
    LOCAL_OLLAMA = "local_ollama"
    LOCAL_LLAMACPP = "local_llamacpp"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DISABLED = "disabled"


REMOTE_PROVIDERS: frozenset[InsightProvider] = frozenset(
    {InsightProvider.ANTHROPIC, InsightProvider.OPENAI}
)


class AiDataSharing(StrEnum):
    DISABLED = "disabled"
    GENERALIZATIONS_ONLY = "generalizations_only"
    AGGREGATES_ONLY = "aggregates_only"
    REDACTED = "redacted"
    FULL = "full"


class InsightCategory(StrEnum):
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    RATIONALE = "rationale"
    QA = "qa"
    CATEGORIZATION = "categorization"
    FORECAST = "forecast"


class OverageBehavior(StrEnum):
    BLOCK = "block"
    WARN_AND_CONTINUE = "warn_and_continue"
    SILENT = "silent"
