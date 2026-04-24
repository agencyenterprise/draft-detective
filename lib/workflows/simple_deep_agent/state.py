"""Shared state and config for simple deep-agent workflows.

All single-node deep-agent workflows share these concrete classes.
The `type` field carries a plain WorkflowRunType (no Literal discriminator)
because deserialization always goes through the manifest's get_state_type(),
not Pydantic union dispatch.
"""

from typing import List, Optional

from langchain_core.messages import BaseMessage
from pydantic import Field, field_serializer

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.simple_deep_agent.agent_types import AgentCheckResult


class SimpleDeepAgentConfig(BaseWorkflowConfig):
    """Shared config for all simple deep-agent workflows."""

    type: WorkflowRunType = Field(
        description="The workflow type, set per-manifest at runtime"
    )


class SimpleDeepAgentState(BaseWorkflowState):
    """Shared state for all simple deep-agent workflows."""

    type: WorkflowRunType = Field(
        description="The workflow type, set per-manifest at runtime"
    )
    config: SimpleDeepAgentConfig
    result: Optional[AgentCheckResult] = Field(
        default=None,
        description="Result from the deep agent validation pass",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="LLM conversation messages from the agent invocation.",
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        return [m.model_dump() for m in messages]
