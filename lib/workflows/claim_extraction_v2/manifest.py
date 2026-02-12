from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_extraction_v2.graph import build_claim_extraction_v2_graph
from lib.workflows.claim_extraction_v2.state import (
    ClaimExtractionV2State,
    ClaimExtractionV2WorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id


class ClaimExtractionV2Manifest(
    WorkflowManifest[ClaimExtractionV2State, ClaimExtractionV2WorkflowConfig]
):
    type = WorkflowRunType.CLAIM_EXTRACTION_V2
    name = "Claim Extraction (v2)"
    description = "Extract claims from documents using paragraph-group based extraction"
    needs_web_search = False
    can_be_triggered_by_user = True  # This is a dependency workflow
    is_internal = False
    required_dependencies = [
        WorkflowRunType.CHUNK_SPLITTING,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
    ]

    def get_state_type(self) -> Type[ClaimExtractionV2State]:
        """Get the type of the workflow state."""
        return ClaimExtractionV2State

    def get_config_type(self) -> Type[ClaimExtractionV2WorkflowConfig]:
        """Get the type of the workflow config."""
        return ClaimExtractionV2WorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_claim_extraction_v2_graph()

    async def create_initial_state(
        self,
        config: ClaimExtractionV2WorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimExtractionV2State:
        """Create and return the initial state of the workflow."""
        return ClaimExtractionV2State(
            type=WorkflowRunType.CLAIM_EXTRACTION_V2,
            file_id=get_main_file_id(existing_states),
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimExtractionV2State, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ClaimExtractionV2State to issues."""
        # Claim extraction doesn't produce issues by itself
        return []
