from abc import ABC, abstractmethod
from typing import List, Type, TypeVar

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
)
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.types import WorkflowState

WorkflowStateType = TypeVar("WorkflowStateType", bound=BaseWorkflowState)
WorkflowConfigType = TypeVar("WorkflowConfigType", bound=BaseWorkflowConfig)


class WorkflowManifest[WorkflowStateType, WorkflowConfigType](ABC):
    """Base class for workflow manifests."""

    type: WorkflowRunType
    name: str
    description: str
    needs_web_search: bool = False

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
    def create_initial_state(
        self, config: WorkflowConfigType, existing_states: List[WorkflowState]
    ) -> WorkflowStateType:
        """Create and return the initial state of the workflow."""

        raise NotImplementedError()

    @abstractmethod
    def convert_state_to_issues(
        self, state: WorkflowStateType, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Get issues for a workflow state result."""

        raise NotImplementedError()
