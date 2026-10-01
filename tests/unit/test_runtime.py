from datetime import datetime
from typing import Any

import pytest

from agent_platform.agents.runtime import AgentRequest, AgentResponse, AgentRuntime, RunContext
from agent_platform.config import Settings
from agent_platform.llm.base import LLMMessage, LLMRequest, LLMResponse, TokenUsage
from agent_platform.telemetry.base import Span, Trace


class FakeProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            provider="test",
            model=request.model,
            content="done",
            usage=TokenUsage(2, 3),
            latency_ms=1.5,
        )


class FakeTelemetry:
    def __init__(self) -> None:
        self.traces: list[Trace] = []
        self.spans: list[Span] = []
        self.llm_calls: list[tuple[Any, ...]] = []
        self.finished: list[tuple[str, str, str | None]] = []

    async def start_trace(self, trace: Trace) -> None:
        self.traces.append(trace)

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error: str | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        self.finished.append((trace_id, status, error))

    async def record_span(self, span: Span) -> None:
        self.spans.append(span)

    async def record_llm_call(self, *args: Any, **kwargs: Any) -> None:
        self.llm_calls.append(args)

    async def record_tool_call(self, *args: Any, **kwargs: Any) -> None:
        return None


class SampleAgent:
    name = "sample"

    async def run(self, request: AgentRequest, context: RunContext) -> AgentResponse:
        response = await context.complete_llm(
            "test",
            LLMRequest("sample-model", [LLMMessage("user", request.message)]),
        )
        return AgentResponse(response.content)


@pytest.mark.asyncio
async def test_runtime_persists_trace_hierarchy_and_llm_call() -> None:
    telemetry = FakeTelemetry()
    runtime = AgentRuntime(
        FakeProvider(),
        telemetry,
        Settings(environment="test", application_version="test"),
    )

    trace_id, response = await runtime.run(SampleAgent(), AgentRequest("hello", user_id="user-1"))

    assert response.message == "done"
    assert telemetry.traces[0].trace_id == trace_id
    assert {span.span_type for span in telemetry.spans} == {"agent", "llm"}
    llm_span = next(span for span in telemetry.spans if span.span_type == "llm")
    assert llm_span.parent_span_id == next(
        span.span_id for span in telemetry.spans if span.span_type == "agent"
    )
    assert telemetry.finished == [(trace_id, "ok", None)]
    assert len(telemetry.llm_calls) == 1
