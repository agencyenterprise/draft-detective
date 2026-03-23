"""Shared types for simple deep-agent workflows.

Defines the canonical IssueItem and AgentCheckResult models used by all
single-node deep-agent workflows, plus the helper that converts them into
DocumentIssue objects.
"""

from typing import List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

from lib.services.chunk_line_matcher import find_chunks_by_line_range
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType


class IssueItem(BaseModel):
    """Lightweight issue returned by a deep agent."""

    title: str = Field(description="Short issue title")
    description: str = Field(
        description="Detailed description of the issue. Supports markdown."
    )
    severity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Issue severity: low, medium, or high",
    )
    long_description: Optional[str] = Field(
        default=None,
        description=(
            "Extended markdown description for issues that require more detail than fits in "
            "description. Use markdown headings, lists, and code blocks to improve readability. "
            "Leave unset when description alone is sufficient."
        ),
    )
    start_line: int = Field(
        description="1-indexed start line in the document where the text relevant to this issue begins",
    )
    end_line: int = Field(
        description="1-indexed end line in the document where the text relevant to this issue ends",
    )


class AgentCheckResult(BaseModel):
    """Result from a single deep-agent validation pass."""

    issues: List[IssueItem] = Field(
        default_factory=list,
        description="Issues found during validation",
    )
    report_markdown: str = Field(
        default="",
        description="Markdown report summarising the check results",
    )


_SEVERITY_MAP = {
    "low": SeverityEnum.LOW,
    "medium": SeverityEnum.MEDIUM,
    "high": SeverityEnum.HIGH,
}


def issues_from_agent_result(
    result: AgentCheckResult,
    workflow_type: WorkflowRunType,
    chunks: Sequence,
) -> List[DocumentIssue]:
    """Convert an AgentCheckResult into DocumentIssue objects."""

    return [
        DocumentIssue(
            title=issue.title,
            type=workflow_type,
            description=issue.description,
            long_description=issue.long_description,
            severity=_SEVERITY_MAP.get(issue.severity.lower(), SeverityEnum.MEDIUM),
            chunk_indices=(
                find_chunks_by_line_range(chunks, issue.start_line, issue.end_line)
                if chunks
                else []
            ),
        )
        for issue in result.issues
    ]
