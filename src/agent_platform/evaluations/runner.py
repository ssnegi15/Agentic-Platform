import asyncio

from agent_platform.evaluations.base import EvaluationCase
from agent_platform.evaluations.deterministic import ExactMatchEvaluator
from agent_platform.evaluations.regression import compare_to_baseline


async def run() -> bool:
    case = EvaluationCase(
        case_id="smoke-001",
        input={"message": "hello"},
        expected_output={"message": "hello"},
    )
    result = await ExactMatchEvaluator().evaluate(case, {"message": "hello"})
    regression = compare_to_baseline(1.0, result.score)
    return result.passed and regression.passed


if __name__ == "__main__":
    passed = asyncio.run(run())
    print("[eval] PASSED" if passed else "[eval] FAILED")
    raise SystemExit(0 if passed else 1)
