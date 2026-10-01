import time
from typing import Any

import httpx

from agent_platform.llm.base import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Works with OpenAI-compatible hosted APIs and self-hosted vLLM endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        provider: str = "openai-compatible",
        timeout_seconds: float = 60,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        started = time.perf_counter()
        try:
            if self._client is None:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
            else:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise LLMProviderError(
                "LLM provider request failed before receiving a response."
            ) from error
        latency_ms = (time.perf_counter() - started) * 1000
        if response.is_error:
            raise LLMProviderError(
                f"LLM provider returned HTTP {response.status_code} "
                f"(request_id={response.headers.get('x-request-id', 'unknown')})."
            )
        try:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result["usage"]
            model = result["model"]
            if not isinstance(content, str) or not isinstance(model, str):
                raise TypeError("Expected string response content and model.")
            input_tokens = int(usage["prompt_tokens"])
            output_tokens = int(usage["completion_tokens"])
            if input_tokens < 0 or output_tokens < 0:
                raise ValueError("Token counts cannot be negative.")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMProviderError(
                "LLM provider returned an invalid completion response."
            ) from error

        return LLMResponse(
            provider=self._provider,
            model=model,
            content=content,
            usage=TokenUsage(input_tokens, output_tokens),
            latency_ms=latency_ms,
            request_id=response.headers.get("x-request-id"),
        )


__all__ = ["LLMProviderError", "OpenAICompatibleProvider", "LLMMessage"]
