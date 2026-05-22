"""Anthropic Claude provider.

Requires the `anthropic` package: pip install anthropic
Privacy restriction: full ai_data_sharing is rejected at the service layer
before this provider is ever invoked. Remote providers never receive raw data.
"""

from decimal import Decimal
from typing import Any

from app.insights.providers.base import CompletionResult, InsightProvider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# USD per million tokens (input, output). Models not listed default to $0.
_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5": (Decimal("0.80"), Decimal("4.00")),
    "claude-haiku-4-5-20251001": (Decimal("0.80"), Decimal("4.00")),
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-7": (Decimal("15.00"), Decimal("75.00")),
}

_MILLION = Decimal("1000000")


def _calc_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    price = _PRICING.get(model)
    if price is None:
        return Decimal("0")
    in_price, out_price = price
    return (in_price * tokens_in + out_price * tokens_out) / _MILLION


class AnthropicProvider(InsightProvider):
    """Wraps the Anthropic Messages API.

    api_key: decrypted from InsightProviderConfig.credentials_encrypted.
    model_name: e.g. "claude-haiku-4-5-20251001", "claude-sonnet-4-6"
    """

    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key
        self._model = model_name or _DEFAULT_MODEL

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> CompletionResult:
        try:
            import anthropic as _sdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package not installed; install with: pip install anthropic"
            ) from exc

        sdk: Any = _sdk
        client: Any = sdk.AsyncAnthropic(api_key=self._api_key)
        response: Any = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = str(response.content[0].text)
        tokens_in = int(response.usage.input_tokens)
        tokens_out = int(response.usage.output_tokens)
        return CompletionResult(
            text=text,
            tokens_used=tokens_in + tokens_out,
            cost=_calc_cost(self._model, tokens_in, tokens_out),
        )

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def get_model_name(self) -> str:
        return self._model
