import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from agent_platform.config import Settings
from agent_platform.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse
from agent_platform.telemetry.base import Span, Telemetry, Trace
from agent_platform.tools.base import Tool


@dataclass(frozen=True)
class AgentRequest:
    message: str
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[LLMMessage] = field(default_factory=list)


@dataclass(frozen=True)
class AgentResponse:
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent(Protocol):
    name: str

    async def run(self, request: AgentRequest, context: "RunContext") -> AgentResponse: ...


class RunContext:
    def __init__(
        self,
        trace_id: str,
        span_id: str,
        llm: LLMProvider,
        telemetry: Telemetry,
        tools: dict[str, Tool],
    ) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self._llm = llm
        self._telemetry = telemetry
        self._tools = tools

    async def complete_llm(self, provider: str, request: LLMRequest) -> LLMResponse:
        span_id = str(uuid4())
        started = datetime.now(UTC)
        timer = time.perf_counter()
        status = "ok"
        try:
            response = await self._llm.complete(request)
        except Exception as error:
            status = "error"
            await self._telemetry.record_llm_call(
                self.trace_id,
                span_id,
                provider,
                request.model,
                (time.perf_counter() - timer) * 1000,
                None,
                request.metadata.get("prompt_version"),
                request.metadata,
                type(error).__name__,
            )
            raise
        finally:
            ended = datetime.now(UTC)
            await self._telemetry.record_span(
                Span(
                    span_id=span_id,
                    trace_id=self.trace_id,
                    parent_span_id=self.span_id,
                    span_type="llm",
                    name=request.model,
                    started_at=started,
                    ended_at=ended,
                    status=status,
                )
            )
        await self._telemetry.record_llm_call(
            self.trace_id,
            span_id,
            response.provider,
            response.model,
            response.latency_ms,
            response,
            request.metadata.get("prompt_version"),
            request.metadata,
        )
        return response

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        safe_input: dict[str, Any] | None = None,
        capture_output: bool = False,
    ) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise LookupError(f"Tool {name!r} is not registered.")
        span_id = str(uuid4())
        started = datetime.now(UTC)
        timer = time.perf_counter()
        status = "ok"
        try:
            result = await tool.execute(arguments)
        except Exception as error:
            status = "error"
            await self._telemetry.record_tool_call(
                self.trace_id,
                span_id,
                name,
                (time.perf_counter() - timer) * 1000,
                "error",
                safe_input=safe_input,
                error=type(error).__name__,
            )
            raise
        finally:
            ended = datetime.now(UTC)
            await self._telemetry.record_span(
                Span(
                    span_id=span_id,
                    trace_id=self.trace_id,
                    parent_span_id=self.span_id,
                    span_type="tool",
                    name=name,
                    started_at=started,
                    ended_at=ended,
                    status=status,
                )
            )
        await self._telemetry.record_tool_call(
            self.trace_id,
            span_id,
            name,
            (time.perf_counter() - timer) * 1000,
            "ok",
            safe_input=safe_input,
            safe_output=result if capture_output and isinstance(result, dict) else None,
        )
        return result


class AgentRuntime:
    def __init__(
        self,
        llm: LLMProvider,
        telemetry: Telemetry,
        settings: Settings,
        tools: dict[str, Tool] | None = None,
    ) -> None:
        self._llm = llm
        self._telemetry = telemetry
        self._settings = settings
        self._tools = tools or {}

    async def run(self, agent: Agent, request: AgentRequest) -> tuple[str, AgentResponse]:
        started = datetime.now(UTC)
        trace_id = str(uuid4())
        span_id = str(uuid4())
        await self._telemetry.start_trace(
            Trace(
                trace_id=trace_id,
                user_id=request.user_id,
                session_id=request.session_id,
                agent=agent.name,
                workflow=None,
                environment=self._settings.environment,
                application_version=self._settings.application_version,
                started_at=started,
            )
        )
        span_started = datetime.now(UTC)
        status = "ok"
        error_name: str | None = None
        try:
            result = await agent.run(
                request,
                RunContext(trace_id, span_id, self._llm, self._telemetry, self._tools),
            )
        except Exception as error:
            status = "error"
            error_name = type(error).__name__
            raise
        finally:
            ended = datetime.now(UTC)
            await self._telemetry.record_span(
                Span(
                    span_id=span_id,
                    trace_id=trace_id,
                    parent_span_id=None,
                    span_type="agent",
                    name=agent.name,
                    started_at=span_started,
                    ended_at=ended,
                    status=status,
                )
            )
            await self._telemetry.finish_trace(trace_id, status, error_name, ended)
        return trace_id, result
