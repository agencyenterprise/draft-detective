"""Base manifest for single-node deep-agent workflows.

The LLM writes a markdown report to the agent filesystem and calls a tool to
report each issue; the node maps both into the ``DeepAgentResult`` stored in
``SimpleDeepAgentState``.

Subclasses declare class-level attributes (type, name, description, and either
`skill` or `user_prompt`) and the usual WorkflowManifest metadata fields.
"""

from typing import TYPE_CHECKING, ClassVar, Literal

from langgraph.graph import START, StateGraph
from langgraph.graph.state import END
from langgraph.runtime import Runtime

from lib.config.llm_models import LLMModel, web_search_tool
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.skills import load_skill_prompt
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.agent_types import (
    DeepAgentResult,
    DeepAgentRun,
    issues_from_agent_result,
    markdown_result_from_run,
)
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
)

if TYPE_CHECKING:
    from lib.workflows.workflow_types import WorkflowState


class SimpleDeepAgentManifest(
    WorkflowManifest[SimpleDeepAgentState, SimpleDeepAgentConfig]
):
    """Deep-agent workflow that writes markdown and reports issues via tools.

    The agent's backend always exposes the full project file tree (current main,
    supporting docs, and a /revisions/<n>/ tree with each revision's main);
    workflows point the agent at the paths they need via the system prompt
    rather than by selecting files here.

    A manifest that declares ``needs_web_search`` gets the web search tool: that
    flag is what gates the user's consent, and the tool is the only way a
    simple deep agent can reach the web, so the two always travel together.
    """

    skill: ClassVar[str | None] = None
    user_prompt: ClassVar[str | None] = None
    system_prompt: ClassVar[str | None] = None

    # Opt-in: when set, the issue tool also accepts proposed edits (verbatim
    # quote plus replacement) that the agent may attach to an issue. Off by
    # default so workflows that only flag problems never see the extra argument.
    propose_edits: ClassVar[bool] = False

    # Per-workflow reasoning effort. None keeps SimpleDeepAgent's default;
    # set it on workflows whose task warrants more deliberation.
    reasoning_effort: ClassVar[Literal["low", "medium", "high"] | None] = None

    # Per-workflow LLM call timeout in seconds. None keeps SimpleDeepAgent's
    # default; raise it on workflows whose turns run long, such as web search.
    llm_timeout: ClassVar[int | None] = None

    # Whether the agent may look at the document's extracted images. Off by
    # default: only workflows whose judgment can hinge on what a figure shows
    # opt in, so text-only checks are not tempted to spend turns on logos.
    view_images: ClassVar[bool] = False

    # The node's label in the run's progress. None uses the workflow's name.
    progress_label: ClassVar[str | None] = None

    def resolve_user_prompt(self) -> str:
        """Resolve the rules/criteria used as the deep agent's user prompt.

        Prefers the referenced skill (the single source of truth) and falls
        back to an inline `user_prompt`. Exactly one must be defined.
        """
        if self.skill is not None:
            return load_skill_prompt(self.skill)
        if self.user_prompt is not None:
            return self.user_prompt
        raise ValueError(
            f"{type(self).__name__} must define either `skill` or `user_prompt`"
        )

    async def prompt_inputs(
        self, state: SimpleDeepAgentState, service: FileArtifactsServiceType
    ) -> str:
        """Per-run inputs appended to the user prompt. Default: none."""
        return ""

    def agent_tools(self, model: LLMModel) -> list[dict]:
        """Workflow tools handed to the agent alongside the issue reporter.

        ``model`` is the one the agent runs on, which the web-search declaration
        has to match.
        """
        if self.needs_web_search:
            return [web_search_tool(model)]
        return []

    def _to_state_result(self, run: DeepAgentRun) -> DeepAgentResult:
        """Map the report file and the reported issues into the state result."""
        return markdown_result_from_run(run)

    def build_graph(self) -> StateGraph:
        manifest = self

        async def run_agent(
            state: SimpleDeepAgentState, runtime: Runtime[ContextSchema]
        ) -> dict:
            service = runtime.context.file_artifacts_service
            agent = SimpleDeepAgent(
                context=runtime.context,
                system_prompt=manifest.system_prompt,
                user_prompt=manifest.resolve_user_prompt()
                + await manifest.prompt_inputs(state, service),
                propose_edits=manifest.propose_edits,
                tools=manifest.agent_tools(
                    runtime.context.agent_model(SimpleDeepAgent.model)
                ),
                reasoning_effort=manifest.reasoning_effort,
                timeout=manifest.llm_timeout,
                view_images=manifest.view_images,
            )
            run = await agent.ainvoke({})
            return {
                "result": manifest._to_state_result(run),
                "messages": run.messages,
            }

        decorated = register_node(self.progress_label or self.name)(run_agent)

        graph = StateGraph(SimpleDeepAgentState, context_schema=ContextSchema)
        graph.add_node("run_agent", decorated)
        graph.add_edge(START, "run_agent")
        graph.add_edge("run_agent", END)
        return graph  # type: ignore[return-value]

    def convert_state_to_issues(
        self,
        state: SimpleDeepAgentState,
        other_states: list["WorkflowState"],
    ) -> list[DocumentIssue]:
        if state.result is None:
            return []
        return issues_from_agent_result(state.result, self.type)
