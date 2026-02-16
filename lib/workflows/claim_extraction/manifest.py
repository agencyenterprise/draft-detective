from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_extraction.graph import build_claim_extraction_graph
from lib.workflows.claim_extraction.state import (
    ClaimExtractionState,
    ClaimExtractionWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id


class ClaimExtractionManifest(
    WorkflowManifest[ClaimExtractionState, ClaimExtractionWorkflowConfig]
):
    type = WorkflowRunType.CLAIM_EXTRACTION
    name = "Claim Extraction"
    description = "Extract and categorize claims from documents"
    needs_web_search = False
    can_be_triggered_by_user = False
    is_internal = True
    required_dependencies = [
        WorkflowRunType.CHUNK_SPLITTING,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
    ]

    def get_state_type(self) -> Type[ClaimExtractionState]:
        """Get the type of the workflow state."""
        return ClaimExtractionState

    def get_config_type(self) -> Type[ClaimExtractionWorkflowConfig]:
        """Get the type of the workflow config."""
        return ClaimExtractionWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_claim_extraction_graph()

    async def create_initial_state(
        self,
        config: ClaimExtractionWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimExtractionState:
        """Create and return the initial state of the workflow."""

        return ClaimExtractionState(
            type=WorkflowRunType.CLAIM_EXTRACTION,
            file_id=get_main_file_id(existing_states),
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimExtractionState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ClaimExtractionState to issues."""
        # Claim extraction doesn't produce issues by itself
        return []
