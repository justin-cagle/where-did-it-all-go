"""Anthropic Claude provider.

Requires the `anthropic` package: pip install anthropic
Privacy restriction: full ai_data_sharing is rejected at the service layer
before this provider is ever invoked. Remote providers never receive raw data.
"""

from decimal import Decimal

from app.insights.providers.base import CompletionResult, InsightProvider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


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

        client = _sdk.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text: str = response.content[0].text  # type: ignore[union-attr]
        tokens_in: int = response.usage.input_tokens
        tokens_out: int = response.usage.output_tokens
        return CompletionResult(
            text=text,
            tokens_used=tokens_in + tokens_out,
            cost=Decimal("0"),  # pricing wired in future iteration
        )

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def get_model_name(self) -> str:
        return self._model
