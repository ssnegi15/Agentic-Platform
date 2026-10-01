from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.evaluations.base import EvaluationResult
from agent_platform.models import EvaluationRun, EvaluationScore


async def persist_evaluation_run(
    session: AsyncSession,
    dataset_id: UUID,
    agent_version: str,
    results: list[tuple[UUID, EvaluationResult]],
    baseline_run_id: UUID | None = None,
) -> EvaluationRun:
    total = len(results)
    passed = sum(result.passed for _, result in results)
    run = EvaluationRun(
        dataset_id=dataset_id,
        agent_version=agent_version,
        baseline_run_id=baseline_run_id,
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        overall_score=(sum(result.score for _, result in results) / total if total else None),
        finished_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add_all(
        [
            EvaluationScore(
                evaluation_run_id=run.id,
                case_id=case_id,
                evaluator=result.evaluator,
                score=result.score,
                passed=result.passed,
                reason=result.reason,
            )
            for case_id, result in results
        ]
    )
    await session.commit()
    return run
