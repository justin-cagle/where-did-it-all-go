"""llama.cpp local inference provider.

Communicates with a locally-running llama.cpp server HTTP API.
"""

from decimal import Decimal

import httpx

from app.insights.providers.base import CompletionResult, InsightProvider

_COMPLETE_TIMEOUT = 120.0
_HEALTH_TIMEOUT = 5.0


class LlamaCppProvider(InsightProvider):
    """Calls llama.cpp server's /completion endpoint.

    base_url: e.g. "http://localhost:8080"
    model_name: identifier used for logging only (llama.cpp loads its model at startup)
    """

    def __init__(self, base_url: str, model_name: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model_name or "llamacpp"

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> CompletionResult:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        async with httpx.AsyncClient(timeout=_COMPLETE_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/completion",
                json={
                    "prompt": full_prompt,
                    "n_predict": max_tokens,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = str(data.get("content", ""))
            tokens = int(data.get("tokens_predicted", 0)) + int(data.get("tokens_evaluated", 0))
            return CompletionResult(text=text, tokens_used=tokens, cost=Decimal("0"))

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self._model
