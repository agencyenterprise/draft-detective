from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.loaders import resolve_input, yaml_dataset
from evals_inspectai.common.scorers import (
    model_graded_check,
    structured_output_scorer,
    tool_called,
)
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={"target_issue_titles": record.get("target_issue_titles", [])},
    )


@task
def figures_tables_check_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    dataset = yaml_dataset(Path(__file__).parent / "dataset.yaml", _record_to_sample)

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "figures_tables_check",
            timeout_s=600,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _compare_issue_titles),
            model_graded_check(partial_credit=True),
            tool_called("view_image"),
        ],
    )


def _compare_issue_titles(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    expected: list[str] = state.metadata.get("target_issue_titles", [])
    actual = [issue.title for issue in output.result.issues] if output.result else []
    return deep_diff_score(expected, actual)
