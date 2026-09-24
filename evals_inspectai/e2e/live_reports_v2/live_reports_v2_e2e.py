"""E2E eval for the live_reports_v2 workflow.

Live Reports searches the web for sources published *after* the document's
publication date that update or challenge its claims, returning the
simple-deep-agent output (`AgentCheckResult`: a list of `issues` plus a
`report_markdown` addendum). Each sample sets an explicit (old) publication
date so that newer post-date sources exist to be found.

Because the recommended sources come from live web search, the output is
non-deterministic — so we score on stable structural signals (issue-count band,
valid line ranges, report contains citations) plus an LLM-graded rubric stored
per-sample in the dataset.
"""

import json
import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score
from inspect_ai.solver import Generate, Solver, TaskState, solver

from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    poll_until_complete,
)
from evals_inspectai.common.api_solver import surface_conversations
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput

_TARGET_WORKFLOW = "live_reports_v2"

# Matches a 4-digit year (19xx/20xx) or a DOI/URL token — used to heuristically
# confirm the report includes full citations for recommended sources.
_CITATION_HINT = re.compile(r"\b(?:19|20)\d{2}\b|https?://|doi\.org|10\.\d{4,}", re.I)


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={
            "publication_date": record.get("publication_date"),
            "min_issues": record.get("min_issues", 0),
            "max_issues": record.get("max_issues"),
            "target_answer": record.get("target_answer", ""),
        },
    )


@solver
def live_reports_v2_solver(
    timeout_s: float = 1800,
    poll_interval_s: float = 5,
) -> Solver:
    """Run live_reports_v2 via the API, passing the sample's publication date.

    A custom solver (rather than the shared ``api_workflow_agent``) is needed
    because Live Reports is date-sensitive: it only searches for sources
    published after the document's publication date, so each sample supplies an
    explicit (old) date via metadata.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        meta = state.metadata or {}

        project_id = await create_project_and_start_workflows(
            file_content=state.input_text,
            file_name="eval-document.md",
            workflow_types=[_TARGET_WORKFLOW],
            publication_date=meta.get("publication_date"),
        )

        try:
            run_detail = await poll_until_complete(
                project_id=project_id,
                workflow_type=_TARGET_WORKFLOW,
                timeout_s=timeout_s,
                interval_s=poll_interval_s,
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}
        await surface_conversations(state, workflow_state, _TARGET_WORKFLOW)

        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return solve


@task
def live_reports_v2_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=live_reports_v2_solver(timeout_s=1800),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _score_structure),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


def _score_structure(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Deterministic structural checks, averaged into a [0, 1] score.

    Exact recommended sources are not asserted (web search is non-deterministic);
    instead we check the output's shape: a result is present with a non-empty
    report, the issue count falls within the sample's expected band, every issue
    carries a sane line range, and — when updates are expected — the report
    includes citation-like detail.
    """
    min_issues: int = state.metadata.get("min_issues", 0)
    max_issues = state.metadata.get("max_issues")

    if output.result is None:
        return Score(value=0.0, explanation="No result in workflow state")

    issues = output.result.issues
    report = output.result.report_markdown or ""

    checks: list[tuple[str, bool]] = []

    checks.append(("report_markdown non-empty", bool(report.strip())))

    count_ok = len(issues) >= min_issues
    if max_issues is not None:
        count_ok = count_ok and len(issues) <= max_issues
    band = f">={min_issues}" + (f" and <={max_issues}" if max_issues is not None else "")
    checks.append((f"issue count {len(issues)} in band ({band})", count_ok))

    line_ranges_ok = all(
        issue.start_line >= 1 and issue.end_line >= issue.start_line
        for issue in issues
    )
    checks.append(("all issues have valid line ranges", line_ranges_ok))

    # Only meaningful when updates are expected: the report should carry full
    # citations (years / DOIs / URLs) for the recommended newer sources.
    if min_issues > 0:
        checks.append(
            ("report includes citation detail", bool(_CITATION_HINT.search(report)))
        )

    passed = sum(1 for _, ok in checks if ok)
    value = passed / len(checks)
    failed = [name for name, ok in checks if not ok]
    explanation = (
        "All structural checks passed"
        if not failed
        else f"Failed: {'; '.join(failed)} ({passed}/{len(checks)} passed)"
    )
    return Score(value=value, explanation=explanation)
