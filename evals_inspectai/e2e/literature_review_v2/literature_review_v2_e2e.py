"""E2E eval for the literature_review_v2 workflow.

Literature Review searches the web for academic sources the document may have
missed, returning the simple-deep-agent output (`AgentCheckResult`: a list of
`issues` plus a `report_markdown`). Because the recommended sources come from
live web search, the output is non-deterministic — so we score on stable
structural signals (issue-count band, valid line ranges, report contains
citations) plus an LLM-graded rubric stored per-sample in the dataset.
"""

import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.common.simple_deep_agent_types import SimpleDeepAgentOutput

# Matches a 4-digit year (19xx/20xx) or a DOI/URL token — used to heuristically
# confirm the report includes full citations for recommended sources.
_CITATION_HINT = re.compile(r"\b(?:19|20)\d{2}\b|https?://|doi\.org|10\.\d{4,}", re.I)


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={
            "min_issues": record.get("min_issues", 0),
            "max_issues": record.get("max_issues"),
            "target_answer": record.get("target_answer", ""),
        },
    )


@task
def literature_review_v2_e2e(
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
        # The full chain (document processing -> reference extraction -> a
        # multi-step web-search deep agent whose own per-call LLM timeout is
        # already 600s) regularly approaches 600s, so allow generous headroom.
        solver=api_workflow_agent(
            "literature_review_v2",
            timeout_s=1200,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
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
    carries a sane line range, and — when recommendations are expected — the
    report includes citation-like detail.
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
    band = f">={min_issues}" + (
        f" and <={max_issues}" if max_issues is not None else ""
    )
    checks.append((f"issue count {len(issues)} in band ({band})", count_ok))

    line_ranges_ok = all(
        issue.start_line >= 1 and issue.end_line >= issue.start_line for issue in issues
    )
    checks.append(("all issues have valid line ranges", line_ranges_ok))

    # Only meaningful when recommendations are expected: the report should carry
    # full citations (years / DOIs / URLs) for the recommended sources.
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
