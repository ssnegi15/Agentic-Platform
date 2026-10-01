import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from agent_platform.db import session_factory
from agent_platform.llm.base import LLMResponse, TokenUsage
from agent_platform.models import LLMCallRecord, ModelPricing, TraceRecord
from agent_platform.telemetry.base import Trace
from agent_platform.telemetry.postgres import PostgreSQLTelemetry

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Set DATABASE_URL to run PostgreSQL integration tests.",
)


@pytest.mark.asyncio
async def test_telemetry_persists_trace_and_centrally_estimated_cost() -> None:
    sessions = session_factory()
    telemetry = PostgreSQLTelemetry(sessions)
    trace_id = str(uuid4())
    provider = f"test-{trace_id}"
    now = datetime.now(UTC)

    async with sessions() as session:
        session.add(
            ModelPricing(
                provider=provider,
                model="test-model",
                input_cost_per_million=2,
                output_cost_per_million=4,
                effective_from=now - timedelta(minutes=1),
            )
        )
        await session.commit()

    try:
        await telemetry.start_trace(
            Trace(
                trace_id=trace_id,
                user_id="integration-test",
                session_id=None,
                agent="integration-test",
                workflow=None,
                environment="test",
                application_version="test",
                started_at=now,
            )
        )
        response = LLMResponse(
            provider=provider,
            model="test-model",
            content="ok",
            usage=TokenUsage(input_tokens=3, output_tokens=5),
            latency_ms=6,
        )
        await telemetry.record_llm_call(
            trace_id,
            str(uuid4()),
            provider,
            "test-model",
            6,
            response,
            "test-prompt-v1",
            {"prompt_version": "test-prompt-v1", "message": "must not be stored"},
        )
        await telemetry.finish_trace(trace_id, "ok")

        async with sessions() as session:
            call = await session.scalar(
                select(LLMCallRecord).where(LLMCallRecord.trace_id == trace_id)
            )
            trace = await session.get(TraceRecord, trace_id)
            assert call is not None
            assert trace is not None
            assert call.input_tokens == 3
            assert call.output_tokens == 5
            assert call.total_tokens == 8
            assert call.input_cost_estimated == pytest.approx(0.000006)
            assert call.output_cost_estimated == pytest.approx(0.00002)
            assert call.total_cost_estimated == pytest.approx(0.000026)
            assert call.cost_is_estimated
            assert call.request_metadata == {"prompt_version": "test-prompt-v1"}
            assert trace.status == "ok"
            assert trace.duration_ms is not None
    finally:
        async with sessions() as session:
            trace = await session.get(TraceRecord, trace_id)
            if trace is not None:
                await session.delete(trace)
            pricing = await session.scalar(
                select(ModelPricing).where(ModelPricing.provider == provider)
            )
            if pricing is not None:
                await session.delete(pricing)
            await session.commit()
