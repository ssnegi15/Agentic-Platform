from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_platform.config import get_settings
from agent_platform.llm.base import LLMResponse
from agent_platform.models import LLMCallRecord, SpanRecord, ToolCallRecord, TraceRecord
from agent_platform.pricing import estimate_cost
from agent_platform.telemetry.base import Span, Trace

_SAFE_METADATA_KEYS = {"prompt_version", "request_type", "temperature", "provider_request_id"}


def _duration_ms(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() * 1000, 0)


class PostgreSQLTelemetry:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def start_trace(self, trace: Trace) -> None:
        async with self._sessions() as session:
            session.add(
                TraceRecord(
                    trace_id=trace.trace_id,
                    user_id=trace.user_id,
                    session_id=trace.session_id,
                    agent=trace.agent,
                    workflow=trace.workflow,
                    environment=trace.environment,
                    application_version=trace.application_version,
                    started_at=trace.started_at,
                    ended_at=trace.ended_at,
                    status=trace.status,
                    error=trace.error,
                )
            )
            await session.commit()

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error: str | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        finished_at = ended_at or datetime.now(UTC)
        async with self._sessions() as session:
            trace = await session.get(TraceRecord, trace_id)
            if trace is None:
                raise LookupError(f"Trace {trace_id} does not exist.")
            trace.ended_at = finished_at
            trace.duration_ms = _duration_ms(trace.started_at, finished_at)
            trace.status = status
            trace.error = error
            await session.commit()

    async def record_span(self, span: Span) -> None:
        ended = span.ended_at
        async with self._sessions() as session:
            session.add(
                SpanRecord(
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    parent_span_id=span.parent_span_id,
                    span_type=span.span_type,
                    name=span.name,
                    started_at=span.started_at,
                    ended_at=ended,
                    duration_ms=_duration_ms(span.started_at, ended) if ended else None,
                    status=span.status,
                    metadata_json=span.metadata,
                )
            )
            await session.commit()

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
    ) -> None:
        safe_metadata = {
            key: value for key, value in metadata.items() if key in _SAFE_METADATA_KEYS
        }
        if response and response.request_id:
            safe_metadata["provider_request_id"] = response.request_id
        async with self._sessions() as session:
            cost = (
                await estimate_cost(
                    session,
                    provider,
                    response.model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    datetime.now(UTC),
                )
                if response
                else None
            )
            session.add(
                LLMCallRecord(
                    trace_id=trace_id,
                    span_id=span_id,
                    provider=provider,
                    model=response.model if response else model,
                    input_tokens=response.usage.input_tokens if response else None,
                    output_tokens=response.usage.output_tokens if response else None,
                    total_tokens=response.usage.total_tokens if response else None,
                    input_cost_estimated=cost.input_cost if cost else None,
                    output_cost_estimated=cost.output_cost if cost else None,
                    total_cost_estimated=cost.total_cost if cost else None,
                    cost_is_estimated=True,
                    latency_ms=response.latency_ms if response else latency_ms,
                    prompt_version=prompt_version,
                    request_metadata=safe_metadata,
                    error=error,
                )
            )
            await session.commit()

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
    ) -> None:
        settings = get_settings()
        async with self._sessions() as session:
            session.add(
                ToolCallRecord(
                    trace_id=trace_id,
                    span_id=span_id,
                    tool_name=tool_name,
                    safe_input=safe_input if settings.telemetry_capture_inputs else None,
                    safe_output=safe_output if settings.telemetry_capture_outputs else None,
                    latency_ms=latency_ms,
                    status=status,
                    error=error,
                )
            )
            await session.commit()
