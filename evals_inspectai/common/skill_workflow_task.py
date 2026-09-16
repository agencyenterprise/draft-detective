"""One eval task shape for every skill-declared workflow.

A skill-backed check emits issues with stable titles, so its eval is always the
same: run the workflow through the API on each sample, count issues per title,
compare to the sample's ``target_title_counts``, and have a model grade the
result against ``target_answer``. Only the titles a sample lists are compared,
so a sample can express don't-care on the others, and a clean sample lists its
titles set to 0.

Dataset records (YAML, so the documents read as block scalars)::

    - input: |
        # Report ...                      # or file://path/relative/to/repo
      target_title_counts:
        Passive Voice: 1
        Ambiguous Actor: 0
      target_answer: What a correct result looks like, for the grader.
"""

from collections import Counter
from pathlib import Path

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.loaders import resolve_input, yaml_dataset
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={"target_title_counts": record.get("target_title_counts", {})},
    )


def compare_title_counts(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Per-title issue counts against ``target_title_counts``; unlisted titles are ignored."""
    expected: dict = state.metadata.get("target_title_counts", {})
    issues = output.result.issues if output.result else []
    counts = Counter(issue.title for issue in issues)
    actual = {title: counts.get(title, 0) for title in expected}
    return deep_diff_score(expected, actual)


def skill_workflow_task(
    workflow_type: str, dataset_path: Path, timeout_s: float = 600
) -> Task:
    """The e2e task for one skill-declared workflow."""
    return Task(
        dataset=yaml_dataset(dataset_path, _record_to_sample),
        fail_on_error=0.2,
        solver=api_workflow_agent(workflow_type, timeout_s=timeout_s),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, compare_title_counts),
            model_graded_check(partial_credit=True),
        ],
    )
