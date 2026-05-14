"""Disabled provider — always unavailable, always raises on complete()."""

from decimal import Decimal

from app.insights.providers.base import CompletionResult, InsightProvider


class InsightProviderDisabledError(Exception):
    """Raised when complete() is called on the disabled provider."""


# Backward-compatible alias used in service.py exception handling
InsightProviderDisabled = InsightProviderDisabledError


class DisabledProvider(InsightProvider):
    """No-op provider for households with ai_data_sharing=disabled.

    is_available() always returns False so the service never selects it.
    complete() raises InsightProviderDisabled as a safety net.
    """

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> CompletionResult:
        raise InsightProviderDisabled(
            "AI insights are disabled for this household. "
            "Configure a provider via POST /insights/providers."
        )

    async def is_available(self) -> bool:
        return False

    def get_model_name(self) -> str:
        return "disabled"

    @staticmethod
    def zero_cost() -> Decimal:
        return Decimal("0")
