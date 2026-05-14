"""OpenAI provider.

Requires the `openai` package: pip install openai
Privacy restriction: full ai_data_sharing is rejected at the service layer
before this provider is ever invoked. Remote providers never receive raw data.
"""

from decimal import Decimal
from typing import Any

from app.insights.providers.base import CompletionResult, InsightProvider

_DEFAULT_MODEL = "gpt-4o-mini"


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
        tokens_used = int(response.usage.total_tokens) if response.usage else 0
        return CompletionResult(
            text=text,
            tokens_used=tokens_used,
            cost=Decimal("0"),  # pricing wired in future iteration
        )

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def get_model_name(self) -> str:
        return self._model
