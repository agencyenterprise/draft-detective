"""Convert abbreviation scan v2 state into document issues.

The rules themselves live in the abbreviation-scan skill's own script,
`skills/abbreviation-scan/scripts/build_issues.py`, so that runners outside
Draft Detective (Claude Code, Codex) apply exactly the code this workflow does.
Here the state is handed to it and its results become `DocumentIssue`s, with the
passage of the occurrence each issue is located at.
"""

from collections.abc import Callable
from typing import Any, cast

from lib.skills import load_skill_script
from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType

_WORKFLOW_TYPE = WorkflowRunType.ABBREVIATION_SCAN_V2

_skill_build_issues = cast(
    Callable[[list[dict[str, Any]], bool], list[dict[str, Any]]],
    load_skill_script("abbreviation-scan", "build_issues.py").build_issues,
)


def build_issues(state: AbbreviationScanV2State) -> list[DocumentIssue]:
    """Build the full list of document issues from the abbreviation scan state."""
    occurrences = [
        item.model_dump(exclude={"passage", "ignored_reason"})
        for item in state.abbreviations
    ]
    results = _skill_build_issues(occurrences, state.abbreviations_section_found)

    issues: list[DocumentIssue] = []
    for result in results:
        index = result["occurrence_index"]
        item = state.abbreviations[index] if index is not None else None
        issues.append(
            DocumentIssue(
                title=result["title"],
                description=result["description"],
                severity=SeverityEnum(result["severity"]),
                type=_WORKFLOW_TYPE,
                start_line=result["start_line"],
                end_line=result["end_line"],
                passage=item.passage if item else None,
            )
        )
    return issues
