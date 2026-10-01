from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator

from agent_platform.evaluations.base import EvaluationCase, EvaluationResult


class ExactMatchEvaluator:
    name = "exact_match"

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        passed = actual_output == case.expected_output
        return EvaluationResult(
            self.name,
            float(passed),
            passed,
            None if passed else "Output mismatch.",
        )


class StructuredFieldEvaluator:
    name = "structured_field"

    def __init__(self, field: str) -> None:
        self.name = f"structured_field:{field}"
        self._field = field

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        expected = case.expected_output
        actual = actual_output
        for key in self._field.split("."):
            actual = actual.get(key) if isinstance(actual, Mapping) else None
            expected = expected.get(key) if isinstance(expected, Mapping) else None
        passed = actual == expected
        return EvaluationResult(
            self.name,
            float(passed),
            passed,
            None if passed else "Field mismatch.",
        )


class JSONSchemaEvaluator:
    name = "json_schema"

    def __init__(self, schema: dict[str, Any]) -> None:
        self._validator = Draft202012Validator(schema)

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        errors = sorted(
            self._validator.iter_errors(actual_output),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        passed = not errors
        reason = None if passed else "; ".join(error.message for error in errors[:3])
        return EvaluationResult(self.name, float(passed), passed, reason)


class ThresholdEvaluator:
    def __init__(self, metric: str, maximum: float) -> None:
        if maximum < 0:
            raise ValueError("maximum must be non-negative")
        self.name = f"{metric}_threshold"
        self._metric = metric
        self._maximum = maximum

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        metrics = case.metadata.get("metrics", {})
        value = metrics.get(self._metric) if isinstance(metrics, Mapping) else None
        passed = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value <= self._maximum
        )
        reason = None if passed else f"{self._metric} must be <= {self._maximum}."
        return EvaluationResult(self.name, float(passed), passed, reason)


class ExpectedValueEvaluator:
    def __init__(self, name: str, selector: str, expected: Any = None) -> None:
        self.name = name
        self._selector = selector.split(".")
        self._expected = expected

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        expected = self._expected if self._expected is not None else case.expected_output
        actual = actual_output
        for key in self._selector:
            actual = actual.get(key) if isinstance(actual, Mapping) else None
            expected = expected.get(key) if isinstance(expected, Mapping) else None
        passed = actual == expected
        return EvaluationResult(
            self.name,
            float(passed),
            passed,
            None if passed else "Reference mismatch.",
        )
