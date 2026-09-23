from typing import List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import Field, field_serializer

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class Reviewer2Config(BaseWorkflowConfig):
    """Configuration for the Reviewer 2 workflow."""

    type: Literal[WorkflowRunType.REVIEWER_2] = Field(WorkflowRunType.REVIEWER_2)


class Reviewer2State(BaseWorkflowState):
    """State for the Reviewer 2 workflow."""

    type: Literal[WorkflowRunType.REVIEWER_2] = Field(WorkflowRunType.REVIEWER_2)
    config: Reviewer2Config
    file_id: str = Field(default="", description="Main document file ID")
    peer_review_markdown: Optional[str] = Field(
        default=None,
        description="The peer review document as markdown (Sections 1-4)",
    )
    rebuttal_markdown: Optional[str] = Field(
        default=None,
        description="The rebuttal document as markdown",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="The reviewer agent's full conversation, system prompt included.",
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        # Checkpointer-hydrated states may contain raw dicts in `messages`
        # because reducers can append items that bypass model construction.
        return [m if isinstance(m, dict) else m.model_dump() for m in messages]
