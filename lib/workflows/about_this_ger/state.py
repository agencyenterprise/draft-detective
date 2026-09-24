"""State definitions for About This (GER) workflow."""

from operator import add
from typing import Annotated, List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_serializer

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.simple_deep_agent.agent_types import AgentCheckResult, IssueItem

__all__ = [
    "AgentCheckResult",
    "AgentConversation",
    "IssueItem",
    "AboutThisGerConfig",
    "AboutThisGerState",
]


class AgentConversation(BaseModel):
    """One validator agent's full conversation, system prompt included."""

    name: str = Field(description='Which validator ran it: "preface" or "authors".')
    messages: List[BaseMessage] = Field(default_factory=list)

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        # Checkpointer-hydrated states may contain raw dicts in `messages`
        # because reducers can append items that bypass model construction.
        return [m if isinstance(m, dict) else m.model_dump() for m in messages]


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
    # The two validators run in parallel, so each appends its own conversation.
    agent_conversations: Annotated[List[AgentConversation], add] = Field(
        default_factory=list,
        description="Each validator agent's conversation, for debugging and eval transcripts.",
    )
