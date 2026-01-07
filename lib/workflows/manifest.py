from abc import ABC, abstractmethod
from typing import List, Type, TypeVar

from langgraph.graph import StateGraph

from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    DocumentIssue,
    WorkflowRunType,
)
from lib.workflows.types import WorkflowState

WorkflowStateType = TypeVar("WorkflowStateType", bound=BaseWorkflowState)
WorkflowConfigType = TypeVar("WorkflowConfigType", bound=BaseWorkflowConfig)


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

    # Whether the workflow can be triggered by the user
    can_be_triggered_by_user: bool = True

    # Internal workflows run as dependencies, not shown in UI
    is_internal: bool = False

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
