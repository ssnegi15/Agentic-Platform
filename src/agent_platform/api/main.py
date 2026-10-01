from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from agent_platform import __version__
from agent_platform.api.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ModelPricingRequest,
    ModelPricingResponse,
    PrincipalResponse,
)
from agent_platform.agents.assistant import AssistantAgent
from agent_platform.agents.runtime import AgentRequest, AgentRuntime
from agent_platform.auth import Principal, current_principal, require_role
from agent_platform.config import get_settings
from agent_platform.db import dispose_engine, get_session, session_factory
from agent_platform.llm.openai_compatible import OpenAICompatibleProvider
from agent_platform.models import (
    EvaluationRun,
    LLMCallRecord,
    ModelPricing,
    SpanRecord,
    ToolCallRecord,
    TraceRecord,
)
from agent_platform.telemetry.postgres import PostgreSQLTelemetry


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            application.state.llm_http_client = client
            yield
    finally:
        await dispose_engine()


app = FastAPI(title="Agent Platform", version=__version__, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/v1/me", response_model=PrincipalResponse)
async def me(principal: Principal = Depends(current_principal)) -> PrincipalResponse:
    return PrincipalResponse(
        subject=principal.subject,
        username=principal.username,
        roles=sorted(principal.roles),
        groups=list(principal.groups),
    )


@app.post("/v1/agents/run", response_model=AgentRunResponse)
async def run_agent(
    body: AgentRunRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
) -> AgentRunResponse:
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_default_model:
        raise HTTPException(
            status_code=503,
            detail="LLM_BASE_URL and LLM_DEFAULT_MODEL are required.",
        )
    provider = OpenAICompatibleProvider(
        settings.llm_base_url,
        settings.llm_api_key,
        provider=settings.llm_provider,
        client=request.app.state.llm_http_client,
    )
    runtime = AgentRuntime(
        provider,
        PostgreSQLTelemetry(session_factory()),
        settings,
    )
    try:
        trace_id, response = await runtime.run(
            AssistantAgent(settings.llm_provider, settings.llm_default_model),
            AgentRequest(
                message=body.message,
                user_id=principal.subject,
                session_id=body.session_id,
            ),
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Agent execution failed.") from error
    return AgentRunResponse(trace_id=trace_id, message=response.message, metadata=response.metadata)


@app.get("/v1/metrics/system")
async def system_metrics(
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    latency = await session.execute(
        text(
            "SELECT count(*) AS request_count, "
            "count(*) FILTER (WHERE status = 'ok') AS success_count, "
            "count(*) FILTER (WHERE status != 'ok') AS failure_count, "
            "coalesce(avg(duration_ms), 0) AS average_latency_ms, "
            "coalesce(percentile_cont(0.50) WITHIN GROUP "
            "(ORDER BY duration_ms), 0) AS p50_latency_ms, "
            "coalesce(percentile_cont(0.95) WITHIN GROUP "
            "(ORDER BY duration_ms), 0) AS p95_latency_ms, "
            "coalesce(percentile_cont(0.99) WITHIN GROUP "
            "(ORDER BY duration_ms), 0) AS p99_latency_ms "
            "FROM traces WHERE ended_at IS NOT NULL"
        )
    )
    llm = await session.execute(
        select(
            func.count(LLMCallRecord.id).label("calls"),
            func.coalesce(func.sum(LLMCallRecord.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMCallRecord.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(LLMCallRecord.total_tokens), 0).label("total_tokens"),
            func.sum(LLMCallRecord.total_cost_estimated).label("estimated_cost"),
            func.count(LLMCallRecord.id)
            .filter(LLMCallRecord.total_cost_estimated.is_not(None))
            .label("priced_calls"),
            func.count(LLMCallRecord.id)
            .filter(LLMCallRecord.total_cost_estimated.is_(None))
            .label("unknown_cost_calls"),
        )
    )
    eval_score = await session.scalar(select(func.avg(EvaluationRun.overall_score)))
    request_metrics = dict(latency.mappings().one())
    request_count = request_metrics["request_count"]
    request_metrics["success_rate"] = (
        request_metrics["success_count"] / request_count if request_count else 0
    )
    request_metrics["failure_rate"] = (
        request_metrics["failure_count"] / request_count if request_count else 0
    )
    return {
        "requests": request_metrics,
        "llm": dict(llm.mappings().one()),
        "evaluation_score": eval_score,
        "cost_label": "estimated",
    }


@app.get("/v1/metrics/agents")
async def agent_metrics(
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            "SELECT t.agent, count(*) AS runs, "
            "count(*) FILTER (WHERE t.status = 'ok') AS successful_runs, "
            "count(*) FILTER (WHERE t.status != 'ok') AS errors, "
            "coalesce(avg(t.duration_ms), 0) AS average_latency_ms, "
            "coalesce(sum(l.input_tokens), 0) AS input_tokens, "
            "coalesce(sum(l.output_tokens), 0) AS output_tokens, "
            "sum(l.estimated_cost) AS estimated_cost, "
            "coalesce(sum(l.priced_calls), 0) AS priced_calls, "
            "coalesce(sum(l.unknown_cost_calls), 0) AS unknown_cost_calls "
            "FROM traces t LEFT JOIN ("
            "SELECT trace_id, sum(input_tokens) AS input_tokens, "
            "sum(output_tokens) AS output_tokens, "
            "sum(total_cost_estimated) AS estimated_cost, "
            "count(*) FILTER (WHERE total_cost_estimated IS NOT NULL) AS priced_calls, "
            "count(*) FILTER (WHERE total_cost_estimated IS NULL) AS unknown_cost_calls "
            "FROM llm_calls GROUP BY trace_id"
            ") l ON l.trace_id = t.trace_id "
            "GROUP BY t.agent ORDER BY t.agent"
        )
    )
    agents = [dict(row) for row in result.mappings()]
    for agent in agents:
        agent["success_rate"] = (
            agent["successful_runs"] / agent["runs"] if agent["runs"] else 0
        )
    return agents


@app.get("/v1/metrics/llm")
async def llm_metrics(
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            "SELECT provider, model, count(*) AS requests, "
            "count(*) FILTER (WHERE error IS NOT NULL) AS failures, "
            "coalesce(sum(input_tokens), 0) AS input_tokens, "
            "coalesce(sum(output_tokens), 0) AS output_tokens, "
            "coalesce(sum(total_tokens), 0) AS total_tokens, "
            "sum(total_cost_estimated) AS estimated_cost, "
            "count(*) FILTER (WHERE total_cost_estimated IS NOT NULL) AS priced_calls, "
            "count(*) FILTER (WHERE total_cost_estimated IS NULL) AS unknown_cost_calls, "
            "coalesce(avg(latency_ms), 0) AS average_latency_ms, "
            "coalesce(percentile_cont(0.50) WITHIN GROUP "
            "(ORDER BY latency_ms), 0) AS p50_latency_ms, "
            "coalesce(percentile_cont(0.95) WITHIN GROUP "
            "(ORDER BY latency_ms), 0) AS p95_latency_ms "
            "FROM llm_calls GROUP BY provider, model ORDER BY provider, model"
        )
    )
    return [dict(row) for row in result.mappings()]


@app.get("/v1/metrics/tools")
async def tool_metrics(
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            "SELECT tool_name, count(*) AS invocations, "
            "count(*) FILTER (WHERE status = 'ok') AS successes, "
            "count(*) FILTER (WHERE status != 'ok') AS failures, "
            "coalesce(avg(latency_ms), 0) AS average_latency_ms, "
            "coalesce(percentile_cont(0.50) WITHIN GROUP "
            "(ORDER BY latency_ms), 0) AS p50_latency_ms, "
            "coalesce(percentile_cont(0.95) WITHIN GROUP "
            "(ORDER BY latency_ms), 0) AS p95_latency_ms "
            "FROM tool_calls GROUP BY tool_name ORDER BY tool_name"
        )
    )
    return [dict(row) for row in result.mappings()]


@app.get("/v1/evaluations/runs")
async def evaluation_runs(
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    baseline = aliased(EvaluationRun)
    rows = (
        await session.execute(
            select(EvaluationRun, baseline)
            .outerjoin(baseline, EvaluationRun.baseline_run_id == baseline.id)
            .order_by(EvaluationRun.started_at.desc())
            .limit(100)
        )
    ).all()
    result: list[dict[str, Any]] = []
    for run, baseline_run in rows:
        result.append(
            {
                "id": str(run.id),
                "dataset_id": str(run.dataset_id),
                "agent_version": run.agent_version,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "total_cases": run.total_cases,
                "passed_cases": run.passed_cases,
                "failed_cases": run.failed_cases,
                "overall_score": run.overall_score,
                "baseline_run_id": str(run.baseline_run_id) if run.baseline_run_id else None,
                "baseline_delta": (
                    run.overall_score - baseline_run.overall_score
                    if baseline_run
                    and run.overall_score is not None
                    and baseline_run.overall_score is not None
                    else None
                ),
            }
        )
    return result


@app.post("/v1/admin/model-pricing", response_model=ModelPricingResponse, status_code=201)
async def add_model_pricing(
    body: ModelPricingRequest,
    _: Principal = Depends(require_role("platform-admin")),
    session: AsyncSession = Depends(get_session),
) -> ModelPricingResponse:
    if body.effective_until and body.effective_until <= body.effective_from:
        raise HTTPException(status_code=422, detail="effective_until must follow effective_from.")
    pricing = ModelPricing(**body.model_dump())
    session.add(pricing)
    await session.commit()
    await session.refresh(pricing)
    return ModelPricingResponse(**body.model_dump(), id=pricing.id)


@app.get("/v1/traces/{trace_id}")
async def trace_detail(
    trace_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    trace = await session.get(TraceRecord, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    if trace.user_id != principal.subject and not (
        {"platform-admin", "platform-observer"} & principal.roles
    ):
        raise HTTPException(status_code=404, detail="Trace not found.")
    spans = (
        await session.scalars(select(SpanRecord).where(SpanRecord.trace_id == trace_id))
    ).all()
    llm_calls = (
        await session.scalars(select(LLMCallRecord).where(LLMCallRecord.trace_id == trace_id))
    ).all()
    tool_calls = (
        await session.scalars(select(ToolCallRecord).where(ToolCallRecord.trace_id == trace_id))
    ).all()
    return {
        "trace": {
            "trace_id": trace.trace_id,
            "user_id": trace.user_id,
            "session_id": trace.session_id,
            "agent": trace.agent,
            "workflow": trace.workflow,
            "environment": trace.environment,
            "application_version": trace.application_version,
            "started_at": trace.started_at,
            "ended_at": trace.ended_at,
            "duration_ms": trace.duration_ms,
            "status": trace.status,
            "error": trace.error,
        },
        "spans": [
            {
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "type": span.span_type,
                "name": span.name,
                "started_at": span.started_at,
                "ended_at": span.ended_at,
                "duration_ms": span.duration_ms,
                "status": span.status,
                "metadata": span.metadata_json,
            }
            for span in spans
        ],
        "llm_calls": [
            {
                "provider": call.provider,
                "model": call.model,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "total_tokens": call.total_tokens,
                "input_cost_estimated": call.input_cost_estimated,
                "output_cost_estimated": call.output_cost_estimated,
                "total_cost_estimated": call.total_cost_estimated,
                "latency_ms": call.latency_ms,
                "prompt_version": call.prompt_version,
                "error": call.error,
            }
            for call in llm_calls
        ],
        "tool_calls": [
            {
                "tool": call.tool_name,
                "input": call.safe_input,
                "output": call.safe_output,
                "latency_ms": call.latency_ms,
                "status": call.status,
                "error": call.error,
            }
            for call in tool_calls
        ],
    }
