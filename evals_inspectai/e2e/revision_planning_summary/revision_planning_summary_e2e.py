"""E2E eval for the revision_planning_summary workflow.

The workflow runs the `review-assistant` skill over a reviewed draft plus its
reviewer memos and returns one self-contained HTML document: a Part 1 worklist
for the author, and a Part 2 that reproduces every memo verbatim with a
planning note under each point.

Unlike the other e2e evals, the project this needs cannot be created by a
single upload: the memos have to carry the `reviewer_memo` role, which only the
TUS path can set, and the workflow short-circuits through its precheck if they
are missing. `peer_review_fixture` builds that project and then starts the
workflow against it.

The prose is free-form, so scoring splits in two:

Each scenario's draft and reviewer memos live as markdown under
`evals_inspectai/files/peer_review/<scenario>/`; the dataset references them and
carries the per-scenario expectations.

- `report_structure`, for the rules the skill states outright and that can be
  checked exactly. It reports one metric per rule (memos reproduced verbatim,
  reviewer text inside marked quotes, a valid and gap-free point-ID scheme, a
  self-contained document, a two-part layout with a short first part, and no
  generic-AI voice tells in the workflow's own prose), so a regression names
  itself in the results table rather than averaging away.
- `rubric_criteria`, for the judgement the skill asks for that no rule can
  capture. It grades four criteria independently, each reported as its own
  metric: locating points by content rather than by a number that will move,
  triaging Part 1 into substantial asks versus a count of quick fixes, carrying
  a scope and a suggestion under every point, and the trap the scenario plants.

Each dataset sample plants a specific trap: conflicting reviewers, a compound
bullet that needs sub-point IDs, three reviewers on a commentary where many
asks are out of scope, a memo that refers to everything by a number the
revision will change, and a memo dominated by trivial corrections.
"""

import json
from pathlib import Path

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import Model, ModelOutput, get_model
from inspect_ai.scorer import (
    Score,
    Scorer,
    Target,
    mean,
    scorer,
    stderr,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.viewer import (
    SampleScoreView,
    ScoreColorScale,
    SampleScoreViewSort,
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
    criteria_for,
    extract_report,
    failed_score,
    grade_criteria,
    report_structure,
)

_TARGET_WORKFLOW = "revision_planning_summary"

# Grader for the judged criteria. Set here rather than taking the shared
# `DEFAULT_GRADER_MODEL`, so changing this suite's judge does not silently
# re-grade the other eighteen e2e suites.
GRADER_MODEL = "openai/gpt-5.6-terra"

# The agent reads a whole draft plus every memo at high reasoning effort and
# writes a long HTML document, so it runs well past the default budget.
_WORKFLOW_TIMEOUT_S = 2400


def _record_to_sample(record: dict) -> Sample:
    """Build a sample from one dataset record.

    The draft and the reviewer memos are `file://` references, resolved here.
    Keeping them on disk as markdown rather than embedding them keeps the
    dataset readable and lets the fixture documents be edited as the documents
    they are; the memo's file name is carried through as its display name on
    upload.
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
        # The draft is the sample input so it reaches the grader as the question.
        input=resolve_input(record["draft"]),
        # The scenario's own criterion, shown as the sample target in the
        # viewer. The graded criteria are read from metadata, not from here.
        target=record["rubric"]["scenario_trap"],
        metadata={
            "memos": memos,
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
    diffable where a JSON string of the same length would not be.
    """
    path = Path(__file__).parent / "dataset.yaml"
    records = yaml.safe_load(path.read_text())
    return MemoryDataset(
        samples=[_record_to_sample(record) for record in records],
        name="revision_planning_summary",
        location=str(path),
    )


@solver
def revision_planning_summary_solver(
    timeout_s: float = _WORKFLOW_TIMEOUT_S,
    poll_interval_s: float = 10,
    local_backend: LocalBackend | None = None,
    api_base_url: str | None = None,
) -> Solver:
    """Build a peer-review project from the sample, then run the workflow on it.

    A custom solver rather than the shared `api_workflow_agent` because the
    project needs reviewer memos in place before the workflow starts; see
    `peer_review_fixture`.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        base_url = await resolve_base_url(local_backend, api_base_url)

        meta = state.metadata or {}

        project_id = await setup_peer_review_project(
            draft=state.input_text,
            memos=[
                ReviewerMemo(file_name=m["file_name"], content=m["content"])
                for m in meta["memos"]
            ],
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
        # the transcript, the same way the shared `api_workflow_agent` does.
        # They are lifted out of the state dict rather than copied, so the
        # completion the scorers parse stays just the workflow result.
        raw_messages = workflow_state.pop("messages", [])
        if raw_messages:
            state.messages = messages_from_langchain(convert_to_messages(raw_messages))

        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return solve


# The rubric, decomposed. One prose brief per sample produced a single grade
# that said "something was weak" without saying which judgement, and let one
# poor area drag the rest. Each criterion is now graded on its own and reported
# as its own metric.
#
# The key set has to be identical across every sample: Inspect raises when a
# declared metric key is missing from any sample's score. So a criterion that
# only applies to one scenario lives inside `scenario_trap`, whose text varies
# per sample, rather than becoming a key of its own.
RUBRIC_CRITERIA = (
    "locations_by_content",
    "part1_triage",
    "planning_notes",
    "scenario_trap",
)

# Criteria that hold for every sample. A dataset record may override any of
# these; in practice only `scenario_trap` is set per sample.
SHARED_CRITERIA: dict[str, str] = {
    "locations_by_content": (
        "Every reviewer point is located by what it is about rather than by a number that "
        "will move. Descriptions such as 'the section introducing the five concepts' or "
        "'the concept about overnight minima' satisfy this. Locations given as 'Concept 4', "
        "'Section 3' or 'page 8' do not, because the author's revision renumbers and retitles "
        "sections. Reviewer memos habitually refer to places by number, so carrying those "
        "numbers over as the location is the specific failure to look for."
    ),
    "part1_triage": (
        "Part 1 is the author's worklist, not a retelling of the memos. It separates the "
        "substantial asks, which need real work, from the quick fixes, which are trivial "
        "corrections. Each substantial ask gets one line with its point ID. The quick fixes "
        "are reduced to a count with their IDs listed and are not spelled out individually. "
        "Filing a substantial ask among the quick fixes, or spelling trivia out in Part 1, "
        "both fail this."
    ),
    "planning_notes": (
        "Under each quoted reviewer point in Part 2 there is a compact planning note carrying "
        "three things: the point's scope (document-wide, section-level, or paragraph-level), "
        "where it lives in the draft, and a one or two sentence suggestion for addressing it. "
        "A point reproduced without a planning note, or a note missing the scope or the "
        "suggestion, fails this."
    ),
}


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
            question=state.input_text,
        )

    return score


def _viewer_config() -> ViewerConfig:
    """Log-viewer defaults tuned to how this eval is actually read.

    Two questions come up every run: which check regressed, and whether the
    workflow is stable across epochs. The grid is arranged to answer both at a
    glance, and the long text fields are hidden because they would otherwise
    dominate every row -- the input is a whole draft and the target is a
    paragraph of criterion prose, neither of which is scannable in a table.

    These are defaults, not overrides: they apply until a reviewer customises
    the view in their own browser.
    """
    score_columns = [
        *(
            TaskSamplesColumn.score("report_structure", name)
            for name in STRUCTURE_CHECKS
        ),
        *(TaskSamplesColumn.score("rubric_criteria", name) for name in RUBRIC_CRITERIA),
    ]

    return ViewerConfig(
        task_samples_view=TaskSamplesView(
            name="Checks and epochs",
            columns=[
                TaskSamplesColumn(id="sampleStatus"),
                # Which fixture, and which of its runs. Both matter here: each
                # sample plants a different trap, and the epochs are the
                # determinism read.
                TaskSamplesColumn(id="sampleId"),
                TaskSamplesColumn(id="epoch"),
                *score_columns,
                # The structured-output parse failure surfaces here, and it is
                # frequent enough to be worth a permanent column.
                TaskSamplesColumn(id="error"),
                TaskSamplesColumn(id="duration"),
                # Hidden: the draft and the criterion text are far too long to
                # scan, and token counts cover only the graders, not the
                # workflow.
                TaskSamplesColumn(id="input", visible=False),
                TaskSamplesColumn(id="target", visible=False),
                TaskSamplesColumn(id="answer", visible=False),
                TaskSamplesColumn(id="tokens", visible=False),
            ],
            # Group each sample's epochs together rather than floating failures
            # to the top: comparing epochs of one fixture is the main reading,
            # and the colour scales already make a weak cell obvious.
            sort=[
                TaskSamplesSort(column="sampleId", dir="asc"),
                TaskSamplesSort(column="epoch", dir="asc"),
            ],
            # Ten score columns; rotate the headers and keep rows compact.
            compact_scores=True,
            multiline=False,
            # Full check names do not fit a narrow column.
            score_labels={
                "verbatim": "Verbatim",
                "quoted": "Quoted",
                "id_scheme": "IDs",
                "self_contained": "Self-cont.",
                "two_part_layout": "Layout",
                "voice": "Voice",
                "locations_by_content": "Locations",
                "part1_triage": "Triage",
                "planning_notes": "Notes",
                "scenario_trap": "Trap",
            },
            # Everything is numeric with 1 good. The rubric criteria are no
            # longer categorical C/P/I: they are graded that way and mapped to
            # 1.0 / 0.5 / 0.0 before scoring, so a partial reads as a mid tone
            # rather than needing its own colour role.
            # Every score here is numeric on a fixed 0-to-1 domain, so pin the
            # domain rather than leaving it to the viewer's default, which
            # anchors each palette to that column's *observed* range. Two
            # things go wrong with the default. A check that passes on every
            # run has min == max, no range to map, and paints nothing, so the
            # healthy columns look unevaluated. And an identical score reads
            # differently per column: 0.5 was the floor of `part1_triage`
            # (observed 0.5-1.0) and painted as bad, while the same 0.5 was
            # the midpoint of `scenario_trap` (observed 0.0-1.0) and painted as
            # middling. Pinning 0..1 makes a cell's colour mean the same thing
            # in every column and gives a passing column its full-marks green.
            score_color_scales={
                name: ScoreColorScale(palette="good-high", min=0.0, max=1.0)
                for name in (*STRUCTURE_CHECKS, *RUBRIC_CRITERIA)
            },
            color_scales_enabled=True,
        ),
        sample_score_view=SampleScoreView(
            default="chips",
            sort=SampleScoreViewSort(column="value", dir="asc"),
        ),
    )


@task
def revision_planning_summary_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    return Task(
        dataset=_load_dataset(),
        fail_on_error=0.2,
        solver=revision_planning_summary_solver(
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            report_structure(),
            rubric_criteria(),
        ],
        viewer=_viewer_config(),
    )
