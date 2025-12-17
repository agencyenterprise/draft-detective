from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.issue_converter import convert_state_to_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SubstantiationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState


class ClaimSubstantiationManifest(
    WorkflowManifest[ClaimSubstantiatorState, SubstantiationWorkflowConfig]
):
    type = WorkflowRunType.CLAIM_SUBSTANTIATION
    name = "Claim Substantiation"
    description = "Extract and verify claims from documents, checking them against supporting documents"
    needs_web_search = False

    def get_state_type(self) -> Type[ClaimSubstantiatorState]:
        """Get the type of the workflow state."""
        return ClaimSubstantiatorState

    def get_config_type(self) -> Type[SubstantiationWorkflowConfig]:
        """Get the type of the workflow config."""
        return SubstantiationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""

        return build_claim_substantiator_graph()

    async def create_initial_state(
        self,
        config: SubstantiationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimSubstantiatorState:
        """Create and return the initial state of the workflow."""
        raise ValueError(
            "Claim substantiation workflow should be temporarily started from its own specific endpoint"
        )

    def convert_state_to_issues(
        self, state: ClaimSubstantiatorState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert ClaimSubstantiatorState to issues."""
        return convert_state_to_issues(state, claim_state)
