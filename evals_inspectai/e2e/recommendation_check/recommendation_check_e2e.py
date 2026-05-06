from collections import Counter
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={
            "target_severity_counts": record.get("target_severity_counts", {}),
        },
    )


@task
def recommendation_check_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent("recommendation_check", timeout_s=600),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _compare_severity_counts),
            model_graded_check(partial_credit=True),
        ],
    )


def _compare_severity_counts(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Compare per-severity issue counts to the expected counts.

    Recommendation Check emits one issue per recommendation occurrence:
      - severity 'none' for supported
      - severity 'medium' for partially_supported
      - severity 'high' for unsupported
    Issue titles include free-form paraphrases of the recommendation, so we
    score on the stable signal (counts per bucket) rather than exact titles.
    """
    expected: dict = state.metadata.get("target_severity_counts", {})
    issues = output.result.issues if output.result else []
    actual = dict(Counter(issue.severity for issue in issues))

    for key in ("none", "low", "medium", "high"):
        expected.setdefault(key, 0)
        actual.setdefault(key, 0)

    return deep_diff_score(expected, actual)
