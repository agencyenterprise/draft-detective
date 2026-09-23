"""E2E eval for the reviewer_coverage_report workflow.

The workflow runs the `review-assistant` skill over a reviewed draft, the
revised draft that answers the memos, and the reviewer memos themselves, and
returns one self-contained HTML document for a quality-assurance manager: a
Part 1 carrying the responsiveness verdict, the list of what still needs work,
and a table counting every reviewer point across four verdict categories, then
a Part 2 reproducing each memo verbatim with a verdict under every point.

The project this needs is the fullest of the three review-assistant fixtures:
reviewer memos on the revision they reviewed, plus a *second* revision holding
the revised draft. The workflow refuses to run when the current main document
is the one the reviewers saw, so `peer_review_fixture` builds both revisions
before the workflow is started.

Each scenario's draft and memos are shared with the revision-planning suite;
what is specific here is `revised.md`, written to plant a known mix of verdicts
so there is something exact to check the bookkeeping against.

Scoring is in three parts:

- the six rules shared by every review-assistant output, from
  `review_assistant_scorers`;
- three checks on the coverage report's own bookkeeping: that the verdict table
  accounts for every point exactly once, that the four-verdict scale is
  actually used, and that Part 1 states the sign-off decision. These check that
  the arithmetic holds, not that any individual verdict is right;
- four judged criteria, each graded in its own call, for the parts that are
  judgement: whether the verdicts match what the revised draft does, whether
  Part 1 is decision-grade, whether each verdict carries evidence and a
  content-anchored location, and the trap the scenario plants.
"""

import json
from pathlib import Path

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import Model, ModelOutput, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.viewer import (
    SampleScoreView,
    SampleScoreViewSort,
    ScoreColorScale,
    TaskSamplesColumn,
    TaskSamplesSort,
    TaskSamplesView,
    ViewerConfig,
)
from langchain_core.messages.utils import convert_to_messages

from evals_inspectai.common.backend import local_backend_for, resolve_base_url
from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.common.local_backend import LocalBackend
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.peer_review_fixture import (
    ReviewerMemo,
    run_review_assistant_workflow,
    setup_peer_review_project,
)
from evals_inspectai.common.review_assistant_scorers import (
    STRUCTURE_CHECKS,
    checks_to_score,
    criteria_for,
    extract_report,
    failed_score,
    grade_criteria,
    structure_checks,
)
from evals_inspectai.e2e.reviewer_coverage_report.verdict_checks import (
    check_recommendation,
    check_verdict_table,
    check_verdict_vocabulary,
)

_TARGET_WORKFLOW = "reviewer_coverage_report"

# Grader for the judged criteria, set per suite rather than shared, so changing
# this suite's judge does not silently re-grade any other.
GRADER_MODEL = "openai/gpt-5.6-terra"

# The agent reads two full drafts plus every memo at high reasoning effort and
# writes a long HTML document, so it runs well past the default budget.
_WORKFLOW_TIMEOUT_S = 2400

# What this output specifies on top of the six shared rules.
COVERAGE_CHECKS = ("verdict_table", "verdict_vocabulary", "recommendation")

ALL_STRUCTURE_CHECKS = (*STRUCTURE_CHECKS, *COVERAGE_CHECKS)


def _record_to_sample(record: dict) -> Sample:
    """Build a sample from one dataset record.

    The reviewed draft is the sample input. The revised draft and the memos
    travel in metadata: the solver needs both to build the project, and the
    grader needs the revised draft to judge whether a verdict matches what the
    revision actually did (see `_grading_question`).
    """
    memos = [
        {
            "file_name": Path(ref.removeprefix("file://")).name,
            "content": resolve_input(ref),
        }
        for ref in record["memos"]
    ]
    return Sample(
        id=record["id"],
        input=resolve_input(record["draft"]),
        target=record["rubric"]["scenario_trap"],
        metadata={
            "memos": memos,
            "revised_draft": resolve_input(record["revised"]),
            "expected_reviewers": record["expected_reviewers"],
            "point_count_bands": record["point_count_bands"],
            "verbatim_probes": record["verbatim_probes"],
            "rubric": record["rubric"],
        },
    )


def _load_dataset() -> MemoryDataset:
    """Read the YAML dataset into memory.

    Inspect ships CSV and JSON loaders but not YAML, so the records are read
    here and handed over as a `MemoryDataset`. YAML is worth that small amount
    of glue for the criterion prose, which folded scalars keep readable and
    diffable where a JSON string of the same length would not.
    """
    path = Path(__file__).parent / "dataset.yaml"
    records = yaml.safe_load(path.read_text())
    return MemoryDataset(
        samples=[_record_to_sample(record) for record in records],
        name="reviewer_coverage_report",
        location=str(path),
    )


@solver
def reviewer_coverage_report_solver(
    timeout_s: float = _WORKFLOW_TIMEOUT_S,
    poll_interval_s: float = 10,
    local_backend: LocalBackend | None = None,
    api_base_url: str | None = None,
) -> Solver:
    """Build the two-revision project from the sample, then run the workflow."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        base_url = await resolve_base_url(local_backend, api_base_url)

        meta = state.metadata or {}

        project_id = await setup_peer_review_project(
            draft=state.input_text,
            memos=[
                ReviewerMemo(file_name=m["file_name"], content=m["content"])
                for m in meta["memos"]
            ],
            revised_draft=meta["revised_draft"],
            base_url=base_url,
        )

        run_detail = await run_review_assistant_workflow(
            project_id=project_id,
            workflow_type=_TARGET_WORKFLOW,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            base_url=base_url,
        )

        workflow_state = run_detail.get("state") or {}

        # Hand the agent's own conversation to Inspect so the log viewer shows
        # the transcript. Lifted out rather than copied, so the completion the
        # scorers parse stays just the workflow result.
        raw_messages = workflow_state.pop("messages", [])
        if raw_messages:
            state.messages = messages_from_langchain(convert_to_messages(raw_messages))

        state.output = ModelOutput(completion=json.dumps(workflow_state), model="api")
        return state

    return solve


@scorer(metrics={name: [mean(), stderr()] for name in ALL_STRUCTURE_CHECKS})
def coverage_structure() -> Scorer:
    """The six shared rules plus this output's verdict bookkeeping.

    One scorer rather than two because all nine checks share the HTML parse,
    which is the expensive part, and Inspect reports each key as its own metric
    either way.
    """

    async def score(state: TaskState, target: Target) -> Score:
        report, reason = extract_report(state)
        if report is None:
            return failed_score(ALL_STRUCTURE_CHECKS, reason)

        checks = structure_checks(report, state.metadata or {})
        checks["verdict_table"] = check_verdict_table(report)
        checks["verdict_vocabulary"] = check_verdict_vocabulary(report)
        checks["recommendation"] = check_recommendation(report)
        return checks_to_score(checks)

    return score


# The judged criteria. Three hold for every scenario; `scenario_trap` carries
# the per-scenario text. The key set has to be identical across samples,
# because Inspect raises when a declared metric key is missing from any score.
RUBRIC_CRITERIA = (
    "verdicts_correct",
    "part1_is_decision_grade",
    "evidence_and_location",
    "scenario_trap",
)

SHARED_CRITERIA: dict[str, str] = {
    "verdicts_correct": (
        "Each reviewer point carries a verdict that matches what the revised draft actually "
        "does, on this scale: addressed (the revision resolves the point), partially addressed "
        "(some of the point was handled), declined with rationale (deliberately not changed, "
        "with a reason that is either stated in the revision or follows from what kind of "
        "document it is), and not addressed (no change and no reason). Only 'not addressed' "
        "should read as a gap. Recording a reasoned decline as a gap, or a silent omission as "
        "a decline, both fail this."
    ),
    "part1_is_decision_grade": (
        "Part 1 answers the one question the QA manager has. It opens with the document type "
        "and the reviewers, gives the overall responsiveness read, and states an explicit "
        "recommendation to sign off or to return the revision for another pass. It then lists "
        "every not-addressed point and every partially addressed point whose remainder is "
        "consequential, one line each with its point ID and what is still missing, and says so "
        "in a single line when there is nothing to list. Nothing else belongs there: a point "
        "that is addressed or declined with rationale is counted in the verdict table and gets "
        "no entry of its own."
    ),
    "evidence_and_location": (
        "Under each quoted reviewer point in Part 2 there is the verdict, the point's location "
        "in the draft described by content rather than by a section or page number, and brief "
        "evidence: what changed in the revised draft, or the reason it was deliberately left "
        "alone. A verdict asserted with no evidence, or a location given as a number, fails "
        "this."
    ),
}


def _grading_question(state: TaskState) -> str:
    """Both drafts, labelled, as the question put to the grader.

    Passing only the reviewed draft made `verdicts_correct` unjudgeable and
    actively wrong: the grader compared the report's claims about what changed
    against the draft that had *not* changed, concluded the revisions were
    fabricated, and marked accurate verdicts as incorrect. Deciding whether a
    point was addressed, partly addressed, declined or ignored requires seeing
    what the revision actually did.
    """
    revised = (state.metadata or {}).get("revised_draft", "")
    return (
        "There are two versions of the document. The reviewer memos were "
        "written against the first; the second is the author's revision "
        "answering them.\n\n"
        "=== REVIEWED DRAFT (what the reviewers saw) ===\n"
        f"{state.input_text}\n\n"
        "=== REVISED DRAFT (what the author changed it to) ===\n"
        f"{revised}\n"
    )


@scorer(metrics={name: [mean(), stderr()] for name in RUBRIC_CRITERIA})
def rubric_criteria(model: str | Model | None = None) -> Scorer:
    """Grade this suite's four criteria, each in its own grader call.

    The grader is shown the report's rendered text, not its HTML. Reading order
    and headings survive the flattening, which is what these criteria turn on,
    and the markup would otherwise be most of the prompt.
    """

    async def score(state: TaskState, target: Target) -> Score:
        report, reason = extract_report(state)
        if report is None:
            return failed_score(RUBRIC_CRITERIA, reason)

        return await grade_criteria(
            grader=get_model(model) if model else get_model(GRADER_MODEL),
            keys=RUBRIC_CRITERIA,
            criteria=criteria_for(state, SHARED_CRITERIA),
            answer=report.raw_text,
            question=_grading_question(state),
        )

    return score


def _viewer_config() -> ViewerConfig:
    """Log-viewer defaults tuned to how this eval is read.

    Which check regressed, and whether the workflow is stable across epochs.
    The long text fields are hidden: the input is a whole draft and the target
    is a paragraph of criterion prose, neither of which is scannable in a table.
    """
    score_columns = [
        *(
            TaskSamplesColumn.score("coverage_structure", name)
            for name in ALL_STRUCTURE_CHECKS
        ),
        *(TaskSamplesColumn.score("rubric_criteria", name) for name in RUBRIC_CRITERIA),
    ]

    return ViewerConfig(
        task_samples_view=TaskSamplesView(
            name="Checks and epochs",
            columns=[
                TaskSamplesColumn(id="sampleStatus"),
                TaskSamplesColumn(id="sampleId"),
                TaskSamplesColumn(id="epoch"),
                *score_columns,
                TaskSamplesColumn(id="error"),
                TaskSamplesColumn(id="duration"),
                TaskSamplesColumn(id="input", visible=False),
                TaskSamplesColumn(id="target", visible=False),
                TaskSamplesColumn(id="answer", visible=False),
                TaskSamplesColumn(id="tokens", visible=False),
            ],
            # Group each scenario's epochs together: comparing repeats of one
            # fixture is the main reading, and the colour scales already make a
            # weak cell obvious.
            sort=[
                TaskSamplesSort(column="sampleId", dir="asc"),
                TaskSamplesSort(column="epoch", dir="asc"),
            ],
            compact_scores=True,
            multiline=False,
            score_labels={
                "verbatim": "Verbatim",
                "quoted": "Quoted",
                "id_scheme": "IDs",
                "self_contained": "Self-cont.",
                "two_part_layout": "Layout",
                "voice": "Voice",
                "verdict_table": "Table",
                "verdict_vocabulary": "Scale",
                "recommendation": "Rec.",
                "verdicts_correct": "Verdicts",
                "part1_is_decision_grade": "Part 1",
                "evidence_and_location": "Evidence",
                "scenario_trap": "Trap",
            },
            # Pinned to 0..1 rather than left to the viewer's default, which
            # anchors each palette to that column's observed range: a check that
            # passes everywhere would paint nothing, and an identical score
            # would read differently from one column to the next.
            score_color_scales={
                name: ScoreColorScale(palette="good-high", min=0.0, max=1.0)
                for name in (*ALL_STRUCTURE_CHECKS, *RUBRIC_CRITERIA)
            },
            color_scales_enabled=True,
        ),
        sample_score_view=SampleScoreView(
            default="grid",
            sort=SampleScoreViewSort(column="value", dir="asc"),
        ),
    )


@task
def reviewer_coverage_report_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    return Task(
        dataset=_load_dataset(),
        fail_on_error=0.2,
        solver=reviewer_coverage_report_solver(
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            coverage_structure(),
            rubric_criteria(),
        ],
        viewer=_viewer_config(),
    )
