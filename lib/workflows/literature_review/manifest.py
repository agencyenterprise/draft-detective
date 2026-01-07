from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.literature_review.graph import build_literature_review_graph
from lib.workflows.literature_review.state import (
    LiteratureReviewState,
    LiteratureReviewWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class LiteratureReviewManifest(
    WorkflowManifest[LiteratureReviewState, LiteratureReviewWorkflowConfig]
):
    type = WorkflowRunType.LITERATURE_REVIEW
    name = "Literature Review"
    description = "Performs a literature review related to the claims in the document. Performs web search to find new relevant literature, looking only for literature published before the document publication date."
    needs_web_search = True
    required_dependencies = [
        WorkflowRunType.REFERENCE_EXTRACTION,
    ]

    def get_state_type(self) -> Type[LiteratureReviewState]:
        """Get the type of the workflow state."""
        return LiteratureReviewState

    def get_config_type(self) -> Type[LiteratureReviewWorkflowConfig]:
        """Get the type of the workflow config."""
        return LiteratureReviewWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_literature_review_graph()

    async def create_initial_state(
        self,
        config: LiteratureReviewWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> LiteratureReviewState:
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

        return LiteratureReviewState(
            type=WorkflowRunType.LITERATURE_REVIEW,
            config=config,
            file=doc_processing_state.file,
            references=ref_extraction_state.references,
        )

    def convert_state_to_issues(
        self, state: LiteratureReviewState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert LiteratureReviewState to issues."""
        return []
