from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.methodological_alignment.graph import (
    build_methodological_alignment_graph,
)
from lib.workflows.methodological_alignment.state import (
    MethodologicalAlignmentState,
    MethodologicalAlignmentWorkflowConfig,
)
from lib.workflows.base import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class MethodologicalAlignmentManifest(
    WorkflowManifest[
        MethodologicalAlignmentState, MethodologicalAlignmentWorkflowConfig
    ]
):
    type = WorkflowRunType.METHODOLOGICAL_ALIGNMENT
    name = "Methodological Alignment"
    description = "Analyze and compare the methodology used in the document against typical methods used in the field. Uses web search to find field methods context."
    needs_web_search = True
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

    def get_state_type(self) -> Type[MethodologicalAlignmentState]:
        """Get the type of the workflow state."""
        return MethodologicalAlignmentState

    def get_config_type(self) -> Type[MethodologicalAlignmentWorkflowConfig]:
        """Get the type of the workflow config."""
        return MethodologicalAlignmentWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_methodological_alignment_graph()

    async def create_initial_state(
        self,
        config: MethodologicalAlignmentWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> MethodologicalAlignmentState:
        """Create and return the initial state of the workflow."""
        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        return MethodologicalAlignmentState(file=claim_state.file)

    def convert_state_to_issues(
        self,
        state: MethodologicalAlignmentState,
        claim_state: ClaimSubstantiatorState,
    ) -> List[DocumentIssue]:
        """Convert MethodologicalAlignmentState to issues."""
        return []
