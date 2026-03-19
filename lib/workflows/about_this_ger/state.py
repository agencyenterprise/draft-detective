"""State definitions for About This (GER) workflow."""

from typing import Literal, Optional

from pydantic import Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.simple_deep_agent.types import AgentCheckResult, IssueItem

__all__ = ["AgentCheckResult", "IssueItem", "AboutThisGerConfig", "AboutThisGerState"]


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
