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
        metadata={"target_issue_titles": record.get("target_issue_titles", [])},
    )


@task
def figures_tables_check_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        solver=api_workflow_agent("figures_tables_check"),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _compare_issue_titles),
            model_graded_check(partial_credit=True),
        ],
    )


def _compare_issue_titles(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    expected: list[str] = state.metadata.get("target_issue_titles", [])
    actual = [issue.title for issue in output.result.issues] if output.result else []
    return deep_diff_score(expected, actual)
