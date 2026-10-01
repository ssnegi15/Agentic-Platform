import pytest

from agent_platform.evaluations.base import EvaluationCase
from agent_platform.evaluations.deterministic import (
    ExactMatchEvaluator,
    JSONSchemaEvaluator,
    StructuredFieldEvaluator,
    ThresholdEvaluator,
)
from agent_platform.evaluations.regression import compare_to_baseline


@pytest.mark.asyncio
async def test_exact_and_structured_evaluators() -> None:
    case = EvaluationCase(
        case_id="case-1",
        input={"message": "hello"},
        expected_output={"classification": "greeting"},
    )
    exact = await ExactMatchEvaluator().evaluate(case, case.expected_output)
    structured = await StructuredFieldEvaluator("classification").evaluate(
        case, {"classification": "greeting", "extra": True}
    )
    assert exact.passed
    assert structured.passed


@pytest.mark.asyncio
async def test_schema_and_threshold_evaluators() -> None:
    case = EvaluationCase(
        case_id="case-2",
        input={},
        metadata={"metrics": {"latency_ms": 12}},
    )
    schema = await JSONSchemaEvaluator(
        {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
    ).evaluate(case, {"answer": "yes"})
    threshold = await ThresholdEvaluator("latency_ms", 15).evaluate(case, None)
    assert schema.passed
    assert threshold.passed


def test_baseline_comparison_rejects_regression() -> None:
    assert not compare_to_baseline(0.95, 0.9, allowed_drop=0.02).passed
    assert compare_to_baseline(0.95, 0.93, allowed_drop=0.02).passed
