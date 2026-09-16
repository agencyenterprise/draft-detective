"""Shared types for simple deep-agent workflows.

Defines the canonical IssueItem and AgentCheckResult models used by all
single-node deep-agent workflows, plus the helper that converts them into
DocumentIssue objects.
"""

from typing import Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field

from lib.workflows.models import (
    DocumentIssue,
    ProposedEdit,
    SeverityEnum,
    WorkflowRunType,
)


class IssueItem(BaseModel):
    """Lightweight issue returned by a deep agent."""

    title: str = Field(description="Short issue title")
    description: str = Field(
        description="Detailed description of the issue. Supports markdown."
    )
    severity: Literal["none", "low", "medium", "high"] = Field(
        default="medium",
        description="Issue severity: none, low, medium, or high. Use 'none' for informational items that should be surfaced but do not represent a problem.",
    )
    long_description: Optional[str] = Field(
        default=None,
        description=(
            "Extended markdown description for issues that require more detail than fits in "
            "description. Use markdown headings, lists, and code blocks to improve readability. "
            "Leave unset when description alone is sufficient."
        ),
    )
    suggested_action: Optional[str] = Field(
        default=None,
        description=(
            "A direct, concise recommendation to the author on what to do to resolve this "
            "issue. Markdown is supported."
        ),
    )
    start_line: int = Field(
        description="1-indexed start line in the document where the text relevant to this issue begins",
    )
    end_line: int = Field(
        description="1-indexed end line in the document where the text relevant to this issue ends",
    )
    edits: List[ProposedEdit] = Field(
        default_factory=list,
        description=(
            "Proposed edits resolving this issue, already located in the document. "
            "Empty unless the agent proposed one and it passed validation."
        ),
    )


# --- State-facing result models -----------------------------------------
# Deep agents no longer fill these as terminal structured responses. Markdown
# and HTML reports are read from files; issues are collected through validated
# tool calls. The models remain the state/API contract consumed downstream.


class AgentCheckResult(BaseModel):
    """Persisted result for a validation pass: issues plus a markdown report."""

    issues: List[IssueItem] = Field(
        default_factory=list,
        description="Issues found during validation",
    )
    report_markdown: str = Field(
        default="",
        description="Markdown report summarising the check results",
    )


# The document under review, as mounted on the agent's filesystem.
MAIN_DOCUMENT_PATH = "/main.md"

# Where report workflows are told to write their deliverables.
REPORT_PATH = "/report.html"
MARKDOWN_REPORT_PATH = "/report.md"

# LangGraph super-step budget for one deep-agent run. Two steps per model turn
# (model node + tools node), so this is roughly 250 turns.
#
# Issue reporting is one `report_issue` call per turn in practice -- the eval
# logs show a mean of 1.07-2.12 calls per turn, not one batched call -- so the
# budget now scales with the number of findings, which it did not when issues
# arrived in a single structured response. Web search does not count against it:
# the Responses API resolves it inside a single model call, so it never reaches
# the tools node. The worst run in the current eval set used 31 steps, so this
# is deliberately generous: it is still 20x under LangGraph's own default, which
# is all this needs to be to stay a backstop against a runaway loop rather than
# a ceiling real documents can hit.
DEEP_AGENT_RECURSION_LIMIT = 500


class ReportNotWrittenError(Exception):
    """A report agent finished without writing its required deliverable.

    Raised rather than returning an empty report: a run that produced nothing
    is a failure, and recording it as a successful run with a blank deliverable
    would hide it from both the UI and the evals.
    """

    def __init__(self, path: str, files: List[str]) -> None:
        self.path = path
        super().__init__(
            f"The agent wrote no report at {path}. Files present: {sorted(files)}"
        )


class DeepAgentRun(BaseModel):
    """Everything one deep-agent invocation produced.

    Reports arrive through ``files`` and issues through per-run tool calls. The
    final assistant message is retained for inspection but never parsed as the
    workflow result.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    files: Dict[str, str] = Field(default_factory=dict)
    reported_issues: List[IssueItem] = Field(default_factory=list)
    messages: List[BaseMessage] = Field(default_factory=list)


# --- Unified state result ------------------------------------------------


class DeepAgentResult(BaseModel):
    """Unified result stored in the workflow state.

    Holds the superset of what the deep-agent variants produce. Exactly one
    report field is populated per run (markdown workflows fill
    ``report_markdown``; HTML workflows fill ``report_html``); the UI renders
    whichever is present. ``issues`` is populated by the markdown variant only.
    """

    issues: List[IssueItem] = Field(default_factory=list)
    report_markdown: str = Field(default="")
    report_html: str = Field(default="")


def report_file(files: Dict[str, str], path: str) -> str:
    """Read a required, non-empty report file or fail the workflow."""
    report = files.get(path, "").strip()
    if not report:
        raise ReportNotWrittenError(path, list(files))
    return report


def markdown_result_from_run(run: DeepAgentRun) -> DeepAgentResult:
    """Build the persisted markdown result from file and tool deliveries."""
    report = report_file(run.files, MARKDOWN_REPORT_PATH)
    return DeepAgentResult(
        issues=run.reported_issues,
        report_markdown=report,
    )


_SEVERITY_MAP = {
    "none": SeverityEnum.NONE,
    "low": SeverityEnum.LOW,
    "medium": SeverityEnum.MEDIUM,
    "high": SeverityEnum.HIGH,
}


def issues_from_agent_result(
    result: AgentCheckResult | DeepAgentResult,
    workflow_type: WorkflowRunType,
) -> List[DocumentIssue]:
    """Convert a result's issues into DocumentIssue objects.

    Emits line ranges only; ``chunk_indices`` is left unset and derived at
    persistence time from the line range.
    """

    return [
        DocumentIssue(
            title=issue.title,
            type=workflow_type,
            description=issue.description,
            long_description=issue.long_description,
            suggested_action=issue.suggested_action,
            severity=_SEVERITY_MAP.get(issue.severity.lower(), SeverityEnum.MEDIUM),
            start_line=issue.start_line,
            end_line=issue.end_line,
            edits=list(issue.edits),
        )
        for issue in result.issues
    ]
