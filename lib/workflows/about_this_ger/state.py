"""State definitions for About This (GER) workflow."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class IssueItem(BaseModel):
    """Lightweight issue returned by the deep agent."""

    title: str = Field(description="Short issue title")
    description: str = Field(description="Detailed description of the issue")
    severity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Issue severity: low, medium, or high",
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


class AboutThisGerConfig(BaseWorkflowConfig):
    """Configuration for the About This (GER) workflow."""

    type: Literal[WorkflowRunType.ABOUT_THIS_GER] = Field(
        WorkflowRunType.ABOUT_THIS_GER
    )


class AboutThisGerState(BaseWorkflowState):
    """State for the About This (GER) workflow."""

    type: Literal[WorkflowRunType.ABOUT_THIS_GER] = Field(
        WorkflowRunType.ABOUT_THIS_GER
    )
    config: AboutThisGerConfig

    preface_result: Optional[AgentCheckResult] = Field(
        default=None,
        description="Result from the preface validation deep agent",
    )
    authors_result: Optional[AgentCheckResult] = Field(
        default=None,
        description="Result from the authors validation deep agent",
    )
