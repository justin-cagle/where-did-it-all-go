"""Insights module.

Owns: InsightProvider abstraction (LocalOllama, LocalLlamaCpp, Anthropic,
OpenAI, Disabled), redaction layer, prompt templates, response handling,
token/cost budget management.

AI is additive — app functions fully without any LLM. AI is never on the
critical path of any core feature.
"""

__all__: list[str] = []
