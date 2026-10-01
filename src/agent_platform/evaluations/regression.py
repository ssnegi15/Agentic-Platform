from dataclasses import dataclass


@dataclass(frozen=True)
class RegressionResult:
    baseline_score: float
    current_score: float
    allowed_drop: float
    passed: bool


def compare_to_baseline(
    baseline_score: float,
    current_score: float,
    allowed_drop: float = 0,
) -> RegressionResult:
    if not 0 <= baseline_score <= 1 or not 0 <= current_score <= 1:
        raise ValueError("Evaluation scores must be between 0 and 1.")
    if not 0 <= allowed_drop <= 1:
        raise ValueError("allowed_drop must be between 0 and 1.")
    return RegressionResult(
        baseline_score,
        current_score,
        allowed_drop,
        current_score >= baseline_score - allowed_drop,
    )
