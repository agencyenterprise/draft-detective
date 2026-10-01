"""Shared state and config for simple deep-agent workflows.

All single-node deep-agent workflows share these concrete classes.
The `type` field carries a plain WorkflowRunType (no Literal discriminator)
because deserialization always goes through the manifest's get_state_type(),
not Pydantic union dispatch.
"""

from typing import Dict, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import Field, field_serializer

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.simple_deep_agent.agent_types import DeepAgentResult


class SimpleDeepAgentConfig(BaseWorkflowConfig):
    """Shared config for all simple deep-agent workflows."""

    type: WorkflowRunType = Field(
        description="The workflow type, set per-manifest at runtime"
    )
    input_files: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description=(
            "Files picked for this run, as input slot name -> file IDs. When set, "
            "the agent reads exactly these files, mounted at "
            "/inputs/<slot>/<file_id>.md, instead of finding its inputs in the "
            "project's file tree. Only workflows with an explicit-inputs prompt "
            "accept it."
        ),
    )


class SimpleDeepAgentState(BaseWorkflowState):
    """Shared state for all single-node deep-agent workflows.

    ``result`` is the unified DeepAgentResult; markdown variants fill its
    ``report_markdown`` (+ ``issues``) from file/tool deliveries, while HTML
    variants fill its ``report_html`` from a file.
    """

    type: WorkflowRunType = Field(
        description="The workflow type, set per-manifest at runtime"
    )
    config: SimpleDeepAgentConfig
    result: Optional[DeepAgentResult] = Field(
        default=None,
        description="Result from the deep agent pass (markdown/issues or HTML report)",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="LLM conversation messages from the agent invocation.",
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        # Checkpointer-hydrated states may contain raw dicts in `messages`
        # because reducers can append items that bypass model construction.
        return [m if isinstance(m, dict) else m.model_dump() for m in messages]
