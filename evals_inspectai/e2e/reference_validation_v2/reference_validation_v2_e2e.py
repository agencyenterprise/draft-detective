"""E2E eval for the Reference Validation workflow, labelled field by field.

Declared by ``skills/reference-validation/SKILL.md``; runs through the API like
every other e2e eval. The workflow extracts the document's references and, for
each, searches the web for the cited work, gives each of author, title,
publisher, year and identifier a problem type, and derives a final result.

Ground truth is ``dataset.yaml``: 70 references, each placed alone under a
References heading, labelled per field (see ``records``). They cover correct
citations of many kinds (journal articles, preprints, RAND and CRS reports,
testimony, press releases, databases, homepages, social posts, public laws),
the skill's leniency rules (a year within one, name forms, truncated author
lists, an organization named once as author and publisher), planted errors
(wrong or misspelled authors, a wrong venue, year, title, DOI or arXiv ID, an
arXiv version mismatch, an HTML-rendered title), bare URLs, and fabricated
references.

Scorers: ``validation_checks``, deterministic, one key per check (see
``criteria``), and ``validation_judged``, one grader call per record with a
labeller's rationale.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/reference_validation_v2/reference_validation_v2_e2e.py --epochs 3
"""

import math
from pathlib import Path
from typing import Optional

from inspect_ai import Task, task
from inspect_ai.model import get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.issue_checks import PER_KEY_METRICS
from evals_inspectai.common.issue_judge import gist, grade
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.e2e.reference_validation_v2.criteria import (
    DESCRIPTIONS,
    JUDGE_DESCRIPTIONS,
    KEYS,
    ReferenceValidationOutput,
    ValidationResult,
    reasoning_prompt,
    validation_scores,
)
from evals_inspectai.e2e.reference_validation_v2.records import ReferenceRecord, load_records, reference_dataset

WORKFLOW_TYPE = "reference_validation_v2"
DATASET = Path(__file__).parent / "dataset.yaml"

SCORE_LABELS = {
    "result_correct": "Result",
    "field_accuracy": "Fields",
    "field_author": "Author",
    "field_title": "Title",
    "field_publisher": "Publisher",
    "field_year": "Year",
    "field_identifier": "Identifier",
    "flags_found": "Flags found",
    "no_false_flags": "No false flags",
    "correction_given": "Correction",
    "result_follows_fields": "Step 6",
    "updated_reference_as_specified": "Updated ref",
    "all_fields_reported": "All fields",
    "url_when_found": "URL",
    "reasoning_matches": "Reasoning",
}


def _validation(state: TaskState) -> tuple[Optional[ValidationResult], str]:
    """The run's validation of its one reference, or None with the reason there is none.
    A per-reference error is an infrastructure failure, raised so Inspect retries it."""
    try:
        output = ReferenceValidationOutput.model_validate_json(state.output.completion)
    except ValueError as e:
        return None, f"could not parse the workflow state: {e}"
    if not output.reference_validations:
        return None, "no reference was validated"
    item = output.reference_validations[0]
    if item.error:
        raise WorkflowCompletionError(f"Reference '{item.input_reference}' failed: {item.error}")
    if item.validation_result is None:
        return None, "the reference has no validation result"
    return item.validation_result, ""


def _record(state: TaskState) -> ReferenceRecord:
    return ReferenceRecord.model_validate(state.metadata["record"])


@scorer(metrics=PER_KEY_METRICS)
def validation_checks() -> Scorer:
    """The deterministic checks, one key each (see ``criteria.validation_scores``)."""

    async def score(state: TaskState, target: Target) -> Score:
        result, why = _validation(state)
        if result is None:
            return Score(value={k: 0.0 for k in KEYS}, explanation=why)
        values, explanation = validation_scores(result, _record(state))
        return Score(value=values, explanation=explanation)

    return score


@scorer(metrics=PER_KEY_METRICS)
def validation_judged(calls: int = 1) -> Scorer:
    """Whether the reasoning reaches the labeller's account, on Inspect's ``grader`` role."""

    async def score(state: TaskState, target: Target) -> Score:
        record = _record(state)
        if not record.rationale:
            return Score(value={"reasoning_matches": math.nan}, explanation="no labeller's rationale")
        result, why = _validation(state)
        if result is None:
            return Score(value={"reasoning_matches": 0.0}, explanation=why)
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        value, reasoning = await grade(grader, reasoning_prompt(record, result), calls)
        return Score(value={"reasoning_matches": value}, explanation=gist(reasoning) if value < 1.0 else "matches")

    return score


@task
def reference_validation_v2_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Reference Validation on every reference and score it field by field.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per record; the median grade is kept.
    """
    records = load_records(DATASET)
    columns = [*(("validation_checks", k) for k in KEYS), ("validation_judged", "reasoning_matches")]
    return Task(
        dataset=reference_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "One reference per record, labelled per field against the reference-validation skill: the final "
                "result, each field's problem type (a list accepts any), correction phrases, and whether the "
                "reference is fabricated. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {"validation_checks": DESCRIPTIONS, "validation_judged": JUDGE_DESCRIPTIONS},
        },
        solver=api_workflow_agent(
            WORKFLOW_TYPE, timeout_s=timeout_s, item_messages_key="reference_validations", item_label="reference"
        ),
        scorer=[validation_checks(), validation_judged(calls=judge_calls)],
        fail_on_error=0.2,
        viewer=issue_viewer_config(columns, SCORE_LABELS),
    )
