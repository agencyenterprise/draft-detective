from abc import ABC, abstractmethod
from typing import List, Type, TypeVar

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph, RunnableConfig

from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    DocumentIssue,
    WorkflowRunType,
)
from lib.workflows.workflow_types import WorkflowState

WorkflowStateType = TypeVar("WorkflowStateType", bound=BaseWorkflowState)
WorkflowConfigType = TypeVar("WorkflowConfigType", bound=BaseWorkflowConfig)

# QA Screener workflows - only visible to RAND and ADMIN roles
QA_SCREENER_WORKFLOWS = {
    WorkflowRunType.ADVOCACY_TONE,
    WorkflowRunType.ABOUT_THIS_GER,
}


class WorkflowManifest[WorkflowStateType, WorkflowConfigType](ABC):
    """Base class for workflow manifests."""

    # Type of the workflow
    type: WorkflowRunType

    # Name of the workflow
    name: str

    # Description of the workflow
    description: str

    # Whether the workflow needs web search
    needs_web_search: bool = False

    # Internal workflows run as dependencies, not shown in UI
    is_internal: bool = False

    # Experimental workflows are hidden by default in the UI
    is_experimental: bool = False

    # If True, workflow stays PENDING until explicitly triggered via API
    requires_human_trigger: bool = False

    # If True, workflow always runs even if already completed (when included as dependency)
    # The workflows needs to be idempotent, meaning it can be run multiple times without changing the result and typical execute only "new" content that was not processed in a previous run, reusing cached results from previous runs, like summarization, document conversion, etc (should process only new files in subsequent runs).
    always_run: bool = False

    @property
    def is_qa_screener(self) -> bool:
        """Whether the workflow is part of the QA Screener tool."""
        return self.type in QA_SCREENER_WORKFLOWS

    # List of workflow types that this workflow depends on.
    # Used to determine the order in which the workflows should be run.
    # In case a workflow is started and a required dependency is not completed, running or scheduled to run, the workflow will fail to start with an error.
    required_dependencies: List[WorkflowRunType] = []

    # List of workflow types that this workflow depends on optionally.
    # Used to determine the order in which the workflows should be run.
    # In case a workflow is started and an optional dependency is running or scheduled to run, the workflow will wait until it completes to start; otherwise, it will start immediately.
    optional_dependencies: List[WorkflowRunType] = []

    @abstractmethod
    def get_state_type(self) -> Type[WorkflowStateType]:
        """Get the type of the workflow state."""

        raise NotImplementedError()

    @abstractmethod
    def get_config_type(self) -> Type[WorkflowConfigType]:
        """Get the type of the workflow config."""

        raise NotImplementedError()

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""

        raise NotImplementedError()

    @abstractmethod
    async def create_initial_state(
        self, config: WorkflowConfigType, existing_states: List[WorkflowState]
    ) -> WorkflowStateType:
        """Create and return the initial state of the workflow."""

        raise NotImplementedError()

    @abstractmethod
    def convert_state_to_issues(
        self, state: WorkflowStateType, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Get issues for a workflow state result."""

        raise NotImplementedError()

    async def on_cancel(
        self,
        state: WorkflowStateType,
        app: CompiledStateGraph,
        config: RunnableConfig,
    ) -> None:
        """
        Called when a workflow run is cancelled. Override to persist state cleanup
        via app.aupdate_state(config, updates, as_node=<node_name>).

        The manifest is responsible for choosing as_node since it owns the graph
        structure. Override in manifests that have per-item statuses that would
        otherwise remain stuck in a 'pending' state after cancellation.
        """
