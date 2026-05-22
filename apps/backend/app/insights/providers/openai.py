"""OpenAI provider.

Requires the `openai` package: pip install openai
Privacy restriction: full ai_data_sharing is rejected at the service layer
before this provider is ever invoked. Remote providers never receive raw data.
"""

from decimal import Decimal
from typing import Any

from app.insights.providers.base import CompletionResult, InsightProvider

_DEFAULT_MODEL = "gpt-4o-mini"

# USD per million tokens (input, output). Models not listed default to $0.
_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4-turbo": (Decimal("10.00"), Decimal("30.00")),
    "gpt-4": (Decimal("30.00"), Decimal("60.00")),
}

_MILLION = Decimal("1000000")


def _calc_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    price = _PRICING.get(model)
    if price is None:
        return Decimal("0")
    in_price, out_price = price
    return (in_price * tokens_in + out_price * tokens_out) / _MILLION


class OpenAIProvider(InsightProvider):
    """Wraps the OpenAI Chat Completions API.

    api_key: decrypted from InsightProviderConfig.credentials_encrypted.
    model_name: e.g. "gpt-4o-mini", "gpt-4o"
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
            import openai as _sdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed; install with: pip install openai"
            ) from exc

        sdk: Any = _sdk
        client: Any = sdk.AsyncOpenAI(api_key=self._api_key)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response: Any = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
        )
        text = str(response.choices[0].message.content or "")
        tokens_in = int(response.usage.prompt_tokens) if response.usage else 0
        tokens_out = int(response.usage.completion_tokens) if response.usage else 0
        return CompletionResult(
            text=text,
            tokens_used=tokens_in + tokens_out,
            cost=_calc_cost(self._model, tokens_in, tokens_out),
        )

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def get_model_name(self) -> str:
        return self._model
