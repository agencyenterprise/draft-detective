"""Manifest for footnote extraction workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.footnote_extraction.graph import build_footnote_extraction_graph
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionConfig,
    FootnoteExtractionState,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class FootnoteExtractionManifest(
    WorkflowManifest[FootnoteExtractionState, FootnoteExtractionConfig]
):
    """Manifest for footnote extraction workflow."""

    type = WorkflowRunType.FOOTNOTE_EXTRACTION
    name = "Footnote Extraction"
    description = "Extract structured footnotes from document with marker, text, and reference code"
    needs_web_search = False
    is_internal = True
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
        revision: int,
    ) -> FootnoteExtractionState:
        """
        Create initial state from DOCUMENT_PROCESSING dependency.

        Gets file_id from DOCUMENT_PROCESSING workflow.
        """
        return FootnoteExtractionState(
            type=WorkflowRunType.FOOTNOTE_EXTRACTION,
            config=config,
            file_id=get_main_file_id(existing_states),
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
