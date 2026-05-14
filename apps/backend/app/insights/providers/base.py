"""Abstract base for all insight providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CompletionResult:
    """Result from a provider.complete() call."""

    text: str
    tokens_used: int
    cost: Decimal


class InsightProvider(ABC):
    """Abstract interface every provider must implement.

    Implementations must be safe to call concurrently — no shared mutable state.
    All methods are async; is_available() should be cheap (health-check only).
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> CompletionResult:
        """Send prompt to the LLM and return the response.

        Raises on transport or API errors — caller handles via try/except.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the provider is reachable and configured.

        Should return quickly (cheap health check). False = skip this provider.
        Must never raise.
        """

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier used for audit logging."""
