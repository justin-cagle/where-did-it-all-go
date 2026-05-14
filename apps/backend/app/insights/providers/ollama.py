"""Ollama local inference provider.

Communicates with a locally-running Ollama server via its HTTP API.
Compatible with the Docker Compose Ollama service defined in deployment.md.
"""

from decimal import Decimal

import httpx

from app.insights.providers.base import CompletionResult, InsightProvider

_COMPLETE_TIMEOUT = 120.0
_HEALTH_TIMEOUT = 5.0


class OllamaProvider(InsightProvider):
    """Calls Ollama's /api/generate endpoint.

    base_url: e.g. "http://ollama:11434"
    model_name: e.g. "llama3.2", "mistral"
    """

    def __init__(self, base_url: str, model_name: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model_name or "llama3.2"

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> CompletionResult:
        async with httpx.AsyncClient(timeout=_COMPLETE_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = str(data.get("response", ""))
            # Ollama returns eval_count (output tokens) + prompt_eval_count (input tokens)
            tokens = int(data.get("eval_count", 0)) + int(data.get("prompt_eval_count", 0))
            return CompletionResult(text=text, tokens_used=tokens, cost=Decimal("0"))

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self._model
