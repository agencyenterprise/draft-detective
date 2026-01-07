from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.claim_extraction.graph import build_claim_extraction_graph
from lib.workflows.claim_extraction.state import (
    ClaimExtractionState,
    ClaimExtractionWorkflowConfig,
)
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class ClaimExtractionManifest(
    WorkflowManifest[ClaimExtractionState, ClaimExtractionWorkflowConfig]
):
    type = WorkflowRunType.CLAIM_EXTRACTION
    name = "Claim Extraction"
    description = "Extract and categorize claims from documents"
    needs_web_search = False
    can_be_triggered_by_user = False  # This is a dependency workflow
    is_internal = True
    required_dependencies = [
        WorkflowRunType.DOCUMENT_PROCESSING,
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

        # Get document processing artifacts from dependency workflow
        doc_processing_state = cast(
            DocumentProcessingState,
            get_state_by_type_or_raise(
                WorkflowRunType.DOCUMENT_PROCESSING, existing_states
            ),
        )

        return ClaimExtractionState(
            type=WorkflowRunType.CLAIM_EXTRACTION,
            main_document_summary=doc_processing_state.main_document_summary,
            chunks=doc_processing_state.chunks,
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimExtractionState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ClaimExtractionState to issues."""
        # Claim extraction doesn't produce issues by itself
        return []
