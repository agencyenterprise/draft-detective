from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import build_analyzed_chunks
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class ClaimSubstantiationManifest(
    WorkflowManifest[ClaimSubstantiatorState, SubstantiationWorkflowConfig]
):
    type = WorkflowRunType.CLAIM_SUBSTANTIATION
    name = "Claim Substantiation"
    description = "Extract and verify claims from documents, checking them against supporting documents"
    needs_web_search = False
    is_internal = True
    can_be_triggered_by_user = False
    required_dependencies = [
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.CITATION_DETECTION,
    ]

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

        from lib.workflows.document_processing.state import DocumentProcessingState
        from lib.workflows.reference_extraction.state import ReferenceExtractionState

        # Get document processing artifacts from dependency workflow
        doc_processing_state = cast(
            DocumentProcessingState,
            get_state_by_type_or_raise(
                WorkflowRunType.DOCUMENT_PROCESSING, existing_states
            ),
        )

        # Get extracted references from reference extraction workflow
        ref_extraction_state = cast(
            ReferenceExtractionState,
            get_state_by_type_or_raise(
                WorkflowRunType.REFERENCE_EXTRACTION, existing_states
            ),
        )

        # Build analyzed chunks from existing states
        chunks = build_analyzed_chunks(existing_states)

        return ClaimSubstantiatorState(
            type=WorkflowRunType.CLAIM_SUBSTANTIATION,
            file=doc_processing_state.file,
            supporting_files=doc_processing_state.supporting_files,
            main_document_summary=doc_processing_state.main_document_summary,
            supporting_documents_summaries=doc_processing_state.supporting_documents_summaries,
            chunks=chunks,
            chunk_to_items=doc_processing_state.chunk_to_items,
            references=ref_extraction_state.references,  # Use pre-extracted references
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimSubstantiatorState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ClaimSubstantiatorState to issues."""
        # Issue creation logic moved to reference extraction manifest

        return []
