from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.issue_converter import convert_state_to_issues
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
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

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

        from lib.workflows.claim_substantiation.state import AnalyzedChunk
        from lib.workflows.document_processing.state import DocumentProcessingState

        # Get document processing artifacts from dependency workflow
        doc_processing_state: DocumentProcessingState = get_state_by_type_or_raise(
            WorkflowRunType.DOCUMENT_PROCESSING, existing_states
        )

        # Convert base chunks to AnalyzedChunk (adds empty fields for claims, citations, etc.)
        chunks = [
            AnalyzedChunk(
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                paragraph_index=chunk.paragraph_index,
            )
            for chunk in doc_processing_state.chunks
        ]

        return ClaimSubstantiatorState(
            file=doc_processing_state.file,
            supporting_files=doc_processing_state.supporting_files,
            main_document_summary=doc_processing_state.main_document_summary,
            supporting_documents_summaries=doc_processing_state.supporting_documents_summaries,
            chunks=chunks,
            chunk_to_items=doc_processing_state.chunk_to_items,
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimSubstantiatorState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert ClaimSubstantiatorState to issues."""
        return convert_state_to_issues(state, claim_state)
