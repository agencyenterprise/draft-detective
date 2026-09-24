"""E2E eval for the results_extraction (Reproducibility Check) workflow.

The workflow is a simple deep agent running the `reproducibility-check` skill:
it reports one issue per result it extracts -- reproducible ones as
informational `none` items, so the issue list is the document's full result
inventory -- and writes the summary, inventory table and per-result detail to
`report_markdown`.

Scoring is in two parts, and every check is its own metric rather than one
blended number, so a regression names itself in the results table:

- `inventory_checks`: eleven deterministic rules, in `checks.py`. Seven are
  about the shape of the delivery; four compare the inventory against the
  dataset's ground truth.
- `rubric_criteria`: two judged criteria, in `criteria.py`, each graded three
  times with the median taken so one erratic call cannot move a metric.
  `classification_grounded` is shared by every sample; `sample_expectations`
  is the record's own `target_answer`. Both are graded on the
  requirement-shaped prompt (`REQUIREMENT_TEMPLATE`), not Inspect's
  model-graded-fact template, because they state properties the output must
  have rather than content it should contain.
- `tool_called("view_image")`: on a sample whose document embeds a chart,
  whether the agent looked at it.

Anything the dataset can state as ground truth is checked deterministically
rather than judged. An earlier generic `inventory_complete` criterion, which
asked a grader whether an inventory was complete given only the document, graded
five *identical* 3-result inventories 0, 0.5, 1, 1, 0.5: without per-sample
ground truth the grader re-litigates the grouping on every call. Each dataset
record now carries its `expected_results`, so completeness, classification and
severity ordering are all decided by comparison instead.

The pieces live in sibling modules -- `contract.py` (metric names and the
vocabularies the ground truth is written in), `parsing.py`, `matching.py`,
`checks.py`, `criteria.py`, `viewer.py` -- because the matching and the checks
are each worth reading and testing on their own.
"""

from pathlib import Path

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.scorers import (
    REQUIREMENT_TEMPLATE,
    checks_to_score,
    criteria_for,
    failed_score,
    grade_criteria,
    tool_called,
)
from evals_inspectai.common.simple_deep_agent_types import (
    AgentCheckResult,
    SimpleDeepAgentOutput,
)
from evals_inspectai.e2e.results_extraction.checks import inventory_check_results
from evals_inspectai.e2e.results_extraction.contract import (
    INVENTORY_CHECKS,
    RUBRIC_CRITERIA,
)
from evals_inspectai.e2e.results_extraction.criteria import (
    GRADER_MODEL,
    SHARED_CRITERIA,
    answer_text,
)
from evals_inspectai.e2e.results_extraction.viewer import viewer_config

# Each criterion is graded this many times and the median taken: graders
# disagreed with themselves across repeats of an unchanged output, and this is
# the noisiest half of the suite.
GRADER_CALLS_PER_CRITERION = 3


def _record_to_sample(record: dict) -> Sample:
    """Build a sample from one dataset record.

    `expected_results` is the record's ground-truth inventory: one entry per
    result the document presents, each with the substrings that identify it, the
    reproducibility class it should be given, and how much the document rests on
    it. The count of the required entries is also the floor for `result_count`,
    so there is no separate expected-count field to drift out of sync.

    An entry with `"required": false` is a reading the document supports without
    demanding -- a number stated in a conclusion that could reasonably be folded
    into the figure it came from. Reporting one is not an invention and not a
    miss, so it counts for `no_extras` and `class_accuracy` but not for
    `completeness`. Every other extra still fails `no_extras`, which is what
    keeps over-splitting visible.

    `target_answer` becomes the `sample_expectations` criterion rather than a
    target string, so it is graded in its own call alongside the shared one.
    """
    return Sample(
        id=record["id"],
        input=record["input"],
        target=record.get("target_answer", ""),
        metadata={
            "expected_results": record.get("expected_results", []),
            "expects_no_results": bool(record.get("expects_no_results")),
            "rubric": {"sample_expectations": record.get("target_answer", "")},
        },
    )


def _load_dataset() -> MemoryDataset:
    """Read the YAML dataset into memory.

    Inspect ships CSV and JSON loaders but not YAML, so the records are read
    here and handed over as a `MemoryDataset`. YAML earns that glue twice over:
    the documents are inline as block scalars, which keeps each record readable
    and diffable as one unit, and the rubric prose stays legible where a JSON
    string of the same length would not.
    """
    path = Path(__file__).parent / "dataset.yaml"
    records = yaml.safe_load(path.read_text())
    for record in records:
        if not record.get("expected_results") and not record.get("expects_no_results"):
            raise ValueError(
                f"dataset record {record.get('id')!r} declares no expected_results; "
                "four of the deterministic checks compare against that inventory "
                "and have nothing to check without it. A document that genuinely "
                "presents no results should say so with `expects_no_results: true`"
            )
    return MemoryDataset(
        samples=[_record_to_sample(record) for record in records],
        name="results_extraction",
        location=str(path),
    )


def _extract_result(state: TaskState) -> tuple[AgentCheckResult | None, str]:
    """Parse the workflow state into its result, or explain why it cannot be.

    Returns `(result, "")` on success and `(None, reason)` otherwise, so both
    scorers reject an unusable output the same way and for the same reasons.
    """
    try:
        output = SimpleDeepAgentOutput.model_validate_json(state.output.completion)
    except ValidationError as e:
        return None, f"Could not parse the workflow state: {e}"
    if output.result is None:
        return None, "No result in the workflow state"
    return output.result, ""


@scorer(metrics={name: [mean(), stderr()] for name in INVENTORY_CHECKS})
def inventory_checks() -> Scorer:
    """The deterministic rules, one metric per rule.

    A single scorer returning a dict of eleven values rather than eleven separate
    scorers: the checks share the parse of the workflow state, the label
    extraction and the ground-truth matching, and Inspect reports each key as its
    own metric either way.
    """

    async def score(state: TaskState, target: Target) -> Score:
        result, reason = _extract_result(state)
        if result is None:
            return failed_score(INVENTORY_CHECKS, reason)
        document_lines = len(state.input_text.splitlines())
        return checks_to_score(
            inventory_check_results(result, state.metadata or {}, document_lines)
        )

    return score


@scorer(metrics={name: [mean(), stderr()] for name in RUBRIC_CRITERIA})
def rubric_criteria(model: str | Model | None = None) -> Scorer:
    """Grade this suite's two criteria, each in its own grader call."""

    async def score(state: TaskState, target: Target) -> Score:
        result, reason = _extract_result(state)
        if result is None:
            return failed_score(RUBRIC_CRITERIA, reason)

        return await grade_criteria(
            grader=get_model(model) if model else get_model(GRADER_MODEL),
            keys=RUBRIC_CRITERIA,
            criteria=criteria_for(state, SHARED_CRITERIA),
            answer=answer_text(result),
            question=state.input_text,
            # These criteria state properties the review must have, not content
            # it should contain, so they need the requirement prompt.
            template=REQUIREMENT_TEMPLATE,
            calls_per_criterion=GRADER_CALLS_PER_CRITERION,
        )

    return score


@task
def results_extraction_e2e():
    return Task(
        dataset=_load_dataset(),
        fail_on_error=0.2,
        solver=api_workflow_agent("results_extraction", timeout_s=600),
        scorer=[
            inventory_checks(),
            rubric_criteria(),
            tool_called("view_image"),
        ],
        viewer=viewer_config(),
    )
