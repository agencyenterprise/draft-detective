from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.loaders import yaml_dataset
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=record["input"],
        target=record.get("target_answer", ""),
        metadata={
            "expected_invalid_count": record["expected_invalid_count"],
        },
    )


@task
def inference_validation_v2_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    dataset = yaml_dataset(Path(__file__).parent / "dataset.yaml", _record_to_sample)

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "inference_validation_v2",
            timeout_s=600,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _compare_invalid_count),
            model_graded_check(partial_credit=True),
            # No `tool_called("view_image")` here: this workflow delegates the
            # reading to sub-agents whose transcripts are not persisted, so the
            # orchestrator's messages cannot show the call. The figure samples
            # are built so the outcome scorers only pass if a chart was read.
        ],
    )


def _compare_invalid_count(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Compare the number of reported invalid inferences to the expected count.

    Every issue this workflow reports is an invalid inference: sound reasoning
    is reported as nothing at all, never as an informational (`none`) entry. An
    informational issue is therefore a contract violation and fails the sample
    outright rather than being counted as a finding -- otherwise a run that
    reported the right *number* of the wrong *kind* of result would score full
    marks. Titles are free-form paraphrases of the flaw, so the count of real
    findings is the stable signal to score on.
    """
    expected: int = state.metadata["expected_invalid_count"]
    issues = output.result.issues if output.result else []

    informational = [issue for issue in issues if issue.severity.lower() == "none"]
    if informational:
        return Score(
            value=0.0,
            explanation=(
                f"Reported {len(informational)} informational (severity 'none') "
                f"issue(s); this assessment must report invalid inferences only"
            ),
        )

    actual = len(issues)

    if actual == expected:
        return Score(
            value=1.0,
            explanation=f"Invalid-inference count matches expected ({expected})",
        )
    return Score(
        value=0.0,
        explanation=f"Expected {expected} invalid inferences, got {actual}",
    )
