from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.citation_detection_footnotes.graph import (
    build_citation_detection_footnotes_graph,
)
from lib.workflows.citation_detection_footnotes.state import (
    CitationDetectionFootnotesConfig,
    CitationDetectionFootnotesState,
)
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.footnote_extraction.state import FootnoteExtractionState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class CitationDetectionFootnotesManifest(
    WorkflowManifest[CitationDetectionFootnotesState, CitationDetectionFootnotesConfig]
):
    type = WorkflowRunType.CITATION_DETECTION_FOOTNOTES
    name = "Citation Detection (Footnotes)"
    description = "Detect citations in document chunks using footnote lookup tools"
    needs_web_search = False
    is_internal = True
    required_dependencies = [
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.FOOTNOTE_EXTRACTION,
    ]

    def get_state_type(self) -> Type[CitationDetectionFootnotesState]:
        """Get the type of the workflow state."""
        return CitationDetectionFootnotesState

    def get_config_type(self) -> Type[CitationDetectionFootnotesConfig]:
        """Get the type of the workflow config."""
        return CitationDetectionFootnotesConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_citation_detection_footnotes_graph()

    async def create_initial_state(
        self,
        config: CitationDetectionFootnotesConfig,
        existing_states: List[WorkflowState],
    ) -> CitationDetectionFootnotesState:
        """Create and return the initial state of the workflow."""

        # Get document processing artifacts
        doc_processing_state: DocumentProcessingState = get_state_by_type_or_raise(
            WorkflowRunType.DOCUMENT_PROCESSING, existing_states
        )

        # Get extracted references
        ref_extraction_state: ReferenceExtractionState = get_state_by_type_or_raise(
            WorkflowRunType.REFERENCE_EXTRACTION, existing_states
        )

        # Get extracted footnotes
        footnote_extraction_state: FootnoteExtractionState = get_state_by_type_or_raise(
            WorkflowRunType.FOOTNOTE_EXTRACTION, existing_states
        )

        return CitationDetectionFootnotesState(
            file=doc_processing_state.file,
            references=ref_extraction_state.references,
            footnotes=footnote_extraction_state.footnotes,
            chunks=doc_processing_state.chunks,
            config=config,
        )

    def convert_state_to_issues(
        self,
        state: CitationDetectionFootnotesState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert state to issues."""
        return []
