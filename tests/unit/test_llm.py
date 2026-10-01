import httpx
import pytest

from agent_platform.llm.base import LLMMessage, LLMRequest, TokenUsage
from agent_platform.llm.openai_compatible import LLMProviderError, OpenAICompatibleProvider


def test_token_totals() -> None:
    assert TokenUsage(input_tokens=10, output_tokens=20).total_tokens == 30


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_usage_and_response() -> None:
    async def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example/v1",
            None,
            provider="test",
            client=client,
        )
        result = await provider.complete(LLMRequest("test-model", [LLMMessage("user", "hello")]))

    assert result.content == "hello"
    assert result.provider == "test"
    assert result.usage.total_tokens == 6


@pytest.mark.asyncio
async def test_provider_errors_do_not_expose_response_body() -> None:
    async def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="sensitive provider error detail")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAICompatibleProvider("https://llm.example/v1", None, client=client)
        with pytest.raises(LLMProviderError, match="HTTP 429") as error:
            await provider.complete(LLMRequest("test-model", []))

    assert "sensitive" not in str(error.value)
