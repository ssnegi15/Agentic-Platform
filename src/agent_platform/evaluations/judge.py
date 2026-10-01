import json
from typing import Any

from agent_platform.evaluations.base import EvaluationCase, EvaluationResult
from agent_platform.llm.base import LLMMessage, LLMProvider, LLMRequest


class LLMJudgeEvaluator:
    """LLM-as-judge evaluator whose provider is injected through the internal interface."""

    name = "llm_judge"

    def __init__(self, provider: LLMProvider, model: str, metric: str) -> None:
        self._provider = provider
        self._model = model
        self.name = f"llm_judge:{metric}"

    async def evaluate(self, case: EvaluationCase, actual_output: Any) -> EvaluationResult:
        prompt = {
            "metric": self.name.partition(":")[2],
            "input": case.input,
            "expected": case.expected_output,
            "actual": actual_output,
        }
        response = await self._provider.complete(
            LLMRequest(
                model=self._model,
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "Evaluate the requested metric. Return only JSON with "
                            '{"score": number from 0 to 1, "reason": short string}.'
                        ),
                    ),
                    LLMMessage(role="user", content=json.dumps(prompt, default=str)),
                ],
                temperature=0,
                metadata={"prompt_version": "judge-v1"},
            )
        )
        try:
            result = json.loads(response.content)
            score = float(result["score"])
            reason = str(result["reason"])
            if not 0 <= score <= 1:
                raise ValueError("Score must be between 0 and 1.")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("LLM judge returned an invalid score payload.") from error
        return EvaluationResult(self.name, score, score >= 0.5, reason)
