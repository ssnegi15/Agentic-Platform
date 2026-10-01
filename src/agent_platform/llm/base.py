from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[LLMMessage]
    temperature: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    usage: TokenUsage
    latency_ms: float
    request_id: str | None = None


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
