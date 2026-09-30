"""E2E eval for the Claim Reference Validation workflow, on the issue-inventory structure.

Declared by ``skills/citation-support/SKILL.md``. Drives the path a user takes:
upload the document and its supporting files, wait for the reference-review
gate, approve it, then wait for the workflow to finish. The workflow reports
one record per in-text citation with the evidence-alignment level it assigned;
the eval reads those records as issues titled with the level (see
``criteria.py``), so every citation in a document, supported ones included, is
an expected issue and a citation it did not list is a false positive.

Ground truth is ``dataset.yaml``: one document per level and per boundary the
skill spells out (supported outright, by faithful inference, rounded, with an
immaterial qualifier left out; partially supported by scope overreach on region
and population, and by mixed evidence; unsupported by silence, a contradicted
value, the opposite direction, the right number on a different measure;
unverifiable with no source uploaded); bracketed, caret and superscript
footnote markers and a narrative citation; the same source cited twice for
claims it does and does not back; a real finding attributed to the wrong
paper; a section-length memo with six citations; and a document with none.
Decoys are the lines a correct run does not report: bibliography and footnote
entries, a footnote marker to commentary, claims that cite nothing.

Scorers: the reusable ``issue_checks`` and ``decoy_checks`` (one record per
citation, so matching is ``one_to_one``; ``title_correct`` is level accuracy;
severity follows the level, so it is not checked), this workflow's own
deterministic checks (accuracy by level, evidence quotes verbatim in a
source, cited text verbatim in the document), and two judged criteria (the
rationale gives the source's real reason; the action for an unsupported
citation says what to change).

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/claim_reference_validation_v2/claim_reference_validation_v2_e2e.py --epochs 3
"""

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver

from evals_inspectai.common.api_client import (
    approve_project_gate,
    create_project_and_start_workflows,
    poll_until_complete,
    poll_until_status,
)
from evals_inspectai.common.api_solver import surface_conversations
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.issue_checks import PER_KEY_METRICS, inventory_from_state, issues_from_state
from evals_inspectai.common.model_override import output_model_name
from evals_inspectai.e2e.claim_reference_validation_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    as_issues,
    evidence_scores,
    label_scores,
    quote_scores,
)
from evals_inspectai.e2e.claim_reference_validation_v2.records import (
    CITATIONS_KEY,
    RESULTS,
    SOURCES_KEY,
    load_claim_suite,
    sources_metadata,
)

WORKFLOW_TYPE = "claim_reference_validation_v2"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: one expected issue per in-text citation, anchored on the cited claim and titled with the "
    "evidence-alignment level a correct run assigns (title_correct is level accuracy), carrying the "
    "labeller's account of what the source says. Decoys are bibliography and footnote entries, commentary "
    "footnotes and uncited claims. Severity follows the level and is not checked; no edits are expected. "
    "A NaN metric value means the sample gave that check nothing to judge."
)
OWN_METRICS = {"citation_checks": OWN_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}


@solver
def claim_reference_validation_v2_solver(timeout_s: float = 900, poll_interval_s: float = 5) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        sources = (state.metadata or {}).get(SOURCES_KEY, [])
        project_id = await create_project_and_start_workflows(
            file_content=state.input_text,
            file_name="main.md",
            workflow_types=[WORKFLOW_TYPE],
            supporting_files=[(s["file_name"], s["markdown"]) for s in sources],
        )

        # The run waits in awaiting_approval until the reference review is
        # approved, while its upstream prep runs. Approve it the way a user
        # would; the released run still waits for its dependencies.
        detail = await poll_until_status(
            project_id=project_id,
            workflow_type=WORKFLOW_TYPE,
            target_statuses={"awaiting_approval", "pending", "running", "completed"},
            timeout_s=timeout_s,
            interval_s=poll_interval_s,
        )
        if detail["run"]["status"] == "awaiting_approval":
            await approve_project_gate(project_id)

        try:
            run_detail = await poll_until_complete(
                project_id=project_id, workflow_type=WORKFLOW_TYPE, timeout_s=timeout_s, interval_s=poll_interval_s
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}
        workflow_state[CITATIONS_KEY] = {"issues": as_issues(workflow_state.get("citation_issues") or [])}
        # Each section's validator conversation goes into the transcript.
        await surface_conversations(state, workflow_state, WORKFLOW_TYPE, "section_verifications", "section")
        state.output = ModelOutput(completion=json.dumps(workflow_state), model=output_model_name(run_detail))
        return state

    return solve


@scorer(metrics=PER_KEY_METRICS)
def citation_checks() -> Scorer:
    """This workflow's own deterministic checks: accuracy by level, evidence quotes
    found verbatim in a supporting file, cited text found verbatim in the document."""

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state, RESULTS)
        labels, label_note = label_scores(issues, inventory_from_state(state))
        records = [] if error else json.loads(state.output.completion).get("citation_issues") or []
        evidence, evidence_note = evidence_scores(records, (state.metadata or {}).get(SOURCES_KEY, []))
        quotes, quote_note = quote_scores(records, state.input_text)
        values = {**labels, **evidence, **quotes}
        if error:
            return Score(value={key: 0.0 for key in values}, explanation=error)
        return Score(value=values, explanation=f"{label_note} | {evidence_note} | {quote_note}")

    return score


@task
def claim_reference_validation_v2_e2e(timeout_s: float = 900, judge_calls: int = 1) -> Task:
    """Run Claim Reference Validation on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for the gate and for the workflow run, each.
        judge_calls: Grader calls per graded citation; the median grade is kept.
    """
    suite = load_claim_suite(DATASET)
    return Task(
        dataset=suite.dataset(sources_metadata),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=claim_reference_validation_v2_solver(timeout_s=timeout_s),
        scorer=[*suite.scorers(), citation_checks(), suite.judged(JUDGE_CRITERIA, calls=judge_calls)],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
