from collections import Counter
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput

# Stable issue titles emitted by the advocacy-tone skill, one per check type.
TRIGGER_WORDS_TITLE = "Trigger Words Detected"
ADVOCACY_LANGUAGE_TITLE = "Advocacy Language Detected"
SUBJECTIVE_TONE_TITLE = "Subjective Tone Detected"


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={
            "target_title_counts": record.get("target_title_counts", {}),
        },
    )


@task
def advocacy_tone_v2_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "advocacy_tone_v2",
            timeout_s=600,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _compare_title_counts),
            model_graded_check(partial_credit=True),
        ],
    )


def _compare_title_counts(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Compare per-title issue counts to the expected counts.

    Advocacy & Tone v2 emits one issue per genuine occurrence, with a stable
    title identifying the check type ("Trigger Words Detected",
    "Advocacy Language Detected", "Subjective Tone Detected"). Severities alone
    can't separate advocacy_language from subjective_tone (both "medium"), so we
    score on title counts instead.

    Only the titles listed in ``target_title_counts`` are compared. A sample that
    cares about a single check type lists only that title (don't-care on the
    others), mirroring the v1 eval's per-check expectations; a sample that should
    produce nothing lists all three titles set to 0.
    """
    expected: dict = state.metadata.get("target_title_counts", {})
    issues = output.result.issues if output.result else []
    counts = Counter(issue.title for issue in issues)
    actual = {title: counts.get(title, 0) for title in expected}

    return deep_diff_score(expected, actual)
