from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str | UUID
    input: Any
    expected_output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    evaluator: str
    score: float
    passed: bool
    reason: str | None = None


class Evaluator(Protocol):
    name: str

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult: ...
