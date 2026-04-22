"""Base manifest for simple single-node deep-agent workflows.

Subclasses only need to declare class-level attributes (type, name, description,
user_prompt) and the usual WorkflowManifest metadata fields.
The graph, node, state construction, and issue conversion are all handled here.
"""

from typing import TYPE_CHECKING, ClassVar, List, Optional, Type

from langgraph.graph import START, StateGraph
from langgraph.graph.state import END
from langgraph.runtime import Runtime

from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
)
from lib.workflows.simple_deep_agent.types import issues_from_agent_result

if TYPE_CHECKING:
    from lib.workflows.workflow_types import WorkflowState


class SimpleDeepAgentManifest(
    WorkflowManifest[SimpleDeepAgentState, SimpleDeepAgentConfig]
):
    """Base manifest for workflows with a single deep-agent node.

    Subclasses must define:
        type: WorkflowRunType
        name: str
        description: str
        user_prompt: str   — the rules/criteria to check (used as the human message)

    Optional overrides:
        system_prompt: str  — overrides the default generic system prompt
        include_supporting_files: bool = False
        (plus any WorkflowManifest fields: required_dependencies, order, etc.)
    """

    user_prompt: ClassVar[str]
    system_prompt: ClassVar[Optional[str]] = None
    include_supporting_files: ClassVar[bool] = False

    def get_state_type(self) -> Type[SimpleDeepAgentState]:
        return SimpleDeepAgentState

    def get_config_type(self) -> Type[SimpleDeepAgentConfig]:
        return SimpleDeepAgentConfig

    def build_graph(self) -> StateGraph:
        manifest = self

        async def run_agent(
            state: SimpleDeepAgentState, runtime: Runtime[ContextSchema]
        ) -> dict:
            agent = SimpleDeepAgent(
                context=runtime.context,
                system_prompt=manifest.system_prompt,
                user_prompt=manifest.user_prompt,
                include_supporting_files=manifest.include_supporting_files,
            )
            result, messages = await agent.ainvoke({})
            return {"result": result, "messages": messages}

        decorated = register_node(self.name)(run_agent)

        graph = StateGraph(SimpleDeepAgentState, context_schema=ContextSchema)
        graph.add_node("run_agent", decorated)
        graph.add_edge(START, "run_agent")
        graph.add_edge("run_agent", END)
        return graph

    async def create_initial_state(
        self,
        config: SimpleDeepAgentConfig,
        existing_states: List["WorkflowState"],
        revision: int,
    ) -> SimpleDeepAgentState:
        return SimpleDeepAgentState(type=self.type, config=config)

    def convert_state_to_issues(
        self,
        state: SimpleDeepAgentState,
        other_states: List["WorkflowState"],
    ) -> List[DocumentIssue]:
        if state.result is None:
            return []
        return issues_from_agent_result(state.result, self.type)
