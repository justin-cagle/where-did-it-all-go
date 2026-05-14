"""Insights module.

Owns: InsightProvider abstraction (LocalOllama, LocalLlamaCpp, Anthropic,
OpenAI, Disabled), redaction layer, prompt templates, response handling,
token/cost budget management.

AI is additive — app functions fully without any LLM. AI is never on the
critical path of any core feature.

Public job functions re-exported for stable worker import path:
    from app.insights import generate_insights_job
"""

from app.insights.jobs import generate_insights_job

__all__ = ["generate_insights_job"]
