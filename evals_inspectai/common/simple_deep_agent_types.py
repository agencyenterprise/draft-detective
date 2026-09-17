"""Shared Pydantic mirrors for workflows built on SimpleDeepAgentManifest.

Any e2e eval targeting a workflow that uses ``SimpleDeepAgentManifest`` (i.e.
a single deep-agent node) can import these types instead of redefining them.
They mirror the backend types in ``lib/workflows/simple_deep_agent/agent_types.py``
and the state shape in ``lib/workflows/simple_deep_agent/state.py``.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ProposedEdit(BaseModel):
    """Local mirror of ProposedEdit from lib/workflows/models.py."""

    original_text: str = ""
    replacement_text: str = ""
    start_line: int = 0
    end_line: int = 0
    rationale: str = ""


class IssueItem(BaseModel):
    """Local mirror of IssueItem from simple_deep_agent/agent_types.py."""

    title: str = ""
    description: str = ""
    severity: str = "medium"
    long_description: Optional[str] = None
    suggested_action: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    edits: List[ProposedEdit] = Field(default_factory=list)


class AgentCheckResult(BaseModel):
    """Local mirror of AgentCheckResult from simple_deep_agent/agent_types.py."""

    issues: List[IssueItem] = Field(default_factory=list)
    report_markdown: str = ""


class SimpleDeepAgentOutput(BaseModel):
    """Local mirror of SimpleDeepAgentState returned by the API.

    The workflow state serialised by api_solver carries the AgentCheckResult
    under the ``result`` key, matching SimpleDeepAgentState.result.
    Extra top-level fields (``errors``, ``type``, ``config``) are ignored.
    """

    result: Optional[AgentCheckResult] = None


class AgentHtmlReport(BaseModel):
    """Local mirror of the HTML-carrying half of ``DeepAgentResult``.

    The report-producing workflows no longer use structured output at all --
    the agent writes the document to a file and the node reads it into
    ``DeepAgentResult.report_html`` -- but the state these evals read is
    unchanged, which is why this mirror still works. ``issues`` is present
    because the markdown variant shares the same state model, and is always
    empty here.
    """

    issues: List[IssueItem] = Field(default_factory=list)
    report_html: str = ""


class HtmlReportAgentOutput(BaseModel):
    """Local mirror of SimpleDeepAgentState for HTML-report workflows.

    Same shape as ``SimpleDeepAgentOutput``; only the fields read off
    ``result`` differ.
    """

    result: Optional[AgentHtmlReport] = None
