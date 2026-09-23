"""E2E eval for the methodological_alignment workflow.

The workflow is a simple deep agent running the `methodology-comparison` skill:
it extracts the paper's methodology, characterises the field baseline through
web search, reports each missing standard component or methodological risk as a
line-anchored issue, and writes the full comparison to `report_markdown`.

The field baseline comes from live web search, so the prose is non-deterministic.
Scoring therefore checks the stable signals — the report carries the skill's
core sections and cites its sources, and the risks the document plainly presents
arrive as well-formed issues — and leaves the substance to an LLM-graded rubric
stored per sample in the dataset.
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

# Section headings the skill's report template requires. Matched as headings of
# any level so a reasonable restructuring of the report does not fail the check.
_REQUIRED_SECTIONS = (
    "Extracted Methodology",
    "Field Methods Overview",
    "Alignment with Field Practice",
    "Methodological Rigor and Risks",
    "Suggestions for Improvements",
)

# The skill demands markdown links for every claim about field practice.
_CITATION_LINK = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        target=record.get("target_answer", ""),
        metadata={"min_issues": record.get("min_issues", 0)},
    )


@task
def methodological_alignment_e2e(
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
        # Web search makes this workflow slower than the document-only checks.
        solver=api_workflow_agent(
            "methodological_alignment",
            timeout_s=900,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            structured_output_scorer(SimpleDeepAgentOutput, _score_structure),
            model_graded_check(partial_credit=True),
        ],
    )


def _has_heading(report: str, title: str) -> bool:
    return re.search(rf"^#+\s*{re.escape(title)}\b", report, re.M | re.I) is not None


def _score_structure(output: SimpleDeepAgentOutput, state: TaskState) -> Score:
    """Deterministic structural checks, averaged into a [0, 1] score.

    The comparison itself is judged by the rubric; here we check that the run
    delivered what the skill asks for: a report with every required section and
    web citations, and at least the sample's minimum number of issues, each with
    a sane line range.
    """
    if output.result is None:
        return Score(value=0.0, explanation="No result in workflow state")

    report = output.result.report_markdown or ""
    issues = output.result.issues
    min_issues: int = state.metadata.get("min_issues", 0)

    checks: list[tuple[str, bool]] = [
        ("report_markdown non-empty", bool(report.strip())),
        *(
            (f"report has a '{title}' section", _has_heading(report, title))
            for title in _REQUIRED_SECTIONS
        ),
        ("report cites web sources as links", bool(_CITATION_LINK.search(report))),
        (f"issue count {len(issues)} >= {min_issues}", len(issues) >= min_issues),
        (
            "all issues have valid line ranges",
            all(
                issue.start_line >= 1 and issue.end_line >= issue.start_line
                for issue in issues
            ),
        ),
        (
            "no informational (none) issues",
            all(issue.severity != "none" for issue in issues),
        ),
    ]

    passed = sum(1 for _, ok in checks if ok)
    failed = [name for name, ok in checks if not ok]
    explanation = (
        "All structural checks passed"
        if not failed
        else f"Failed: {'; '.join(failed)} ({passed}/{len(checks)} passed)"
    )
    return Score(value=passed / len(checks), explanation=explanation)
