"""Manifest for footnote extraction workflow."""

from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.footnote_extraction.graph import build_footnote_extraction_graph
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionConfig,
    FootnoteExtractionState,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class FootnoteExtractionManifest(
    WorkflowManifest[FootnoteExtractionState, FootnoteExtractionConfig]
):
    """Manifest for footnote extraction workflow."""

    type = WorkflowRunType.FOOTNOTE_EXTRACTION
    name = "Footnote Extraction"
    description = "Extract structured footnotes from document with marker, text, and reference code"
    needs_web_search = False
    is_internal = True  # Runs as dependency, not user-triggered from workflow list
    can_be_triggered_by_user = True  # Can be used as standalone tool
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[FootnoteExtractionState]:
        """Get the type of the workflow state."""
        return FootnoteExtractionState

    def get_config_type(self) -> Type[FootnoteExtractionConfig]:
        """Get the type of the workflow config."""
        return FootnoteExtractionConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_footnote_extraction_graph()

    async def create_initial_state(
        self,
        config: FootnoteExtractionConfig,
        existing_states: List[WorkflowState],
    ) -> FootnoteExtractionState:
        """
        Create initial state from DOCUMENT_PROCESSING dependency.

        Gets file with markdown from DOCUMENT_PROCESSING workflow.
        """
        # Get document processing artifacts
        doc_processing_state = cast(
            DocumentProcessingState,
            get_state_by_type_or_raise(
                WorkflowRunType.DOCUMENT_PROCESSING, existing_states
            ),
        )

        return FootnoteExtractionState(
            type=WorkflowRunType.FOOTNOTE_EXTRACTION,
            config=config,
            file=doc_processing_state.file,  # Already has markdown populated
        )

    def convert_state_to_issues(
        self,
        state: FootnoteExtractionState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert footnote extraction state to issues."""
        # No issues generated for footnotes
        # Footnotes are informational only - no validation needed
        return []
