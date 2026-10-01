from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from agent_platform.llm.base import LLMResponse


@dataclass(frozen=True)
class Trace:
    trace_id: str
    user_id: str | None
    session_id: str | None
    agent: str
    workflow: str | None
    environment: str
    application_version: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"
    error: str | None = None


@dataclass(frozen=True)
class Span:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    span_type: str
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)


class Telemetry(Protocol):
    async def start_trace(self, trace: Trace) -> None: ...

    async def finish_trace(
        self, trace_id: str, status: str, error: str | None = None, ended_at: datetime | None = None
    ) -> None: ...

    async def record_span(self, span: Span) -> None: ...

    async def record_llm_call(
        self,
        trace_id: str,
        span_id: str,
        provider: str,
        model: str,
        latency_ms: float,
        response: LLMResponse | None,
        prompt_version: str | None,
        metadata: dict[str, Any],
        error: str | None = None,
    ) -> None: ...

    async def record_tool_call(
        self,
        trace_id: str,
        span_id: str,
        tool_name: str,
        latency_ms: float,
        status: str,
        safe_input: dict[str, Any] | None = None,
        safe_output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None: ...
