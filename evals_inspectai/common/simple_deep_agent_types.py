"""Shared Pydantic mirrors for workflows built on SimpleDeepAgentManifest.

Any e2e eval targeting a workflow that uses ``SimpleDeepAgentManifest`` (i.e.
a single deep-agent node) can import these types instead of redefining them.
They mirror the backend types in ``lib/workflows/simple_deep_agent/agent_types.py``
and the state shape in ``lib/workflows/simple_deep_agent/state.py``.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class IssueItem(BaseModel):
    """Local mirror of IssueItem from simple_deep_agent/agent_types.py."""

    title: str = ""
    description: str = ""
    severity: str = "medium"
    long_description: Optional[str] = None
    start_line: int = 0
    end_line: int = 0


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
