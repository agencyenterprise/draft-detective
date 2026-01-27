"""Manifest for document summarization workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.document_summarization.graph import (
    build_document_summarization_graph,
)
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    DocumentSummarizationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id, get_supporting_file_ids


class DocumentSummarizationManifest(
    WorkflowManifest[DocumentSummarizationState, DocumentSummarizationWorkflowConfig]
):
    type = WorkflowRunType.DOCUMENT_SUMMARIZATION
    name = "Document Summarization"
    description = "Summarize the main document and supporting documents"
    needs_web_search = False
    can_be_triggered_by_user = (
        False  # This is a dependency workflow, not directly triggered
    )
    is_internal = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    always_run = True  # Always run document summarization to ensure new files are summarized. The workflow summarizes only new files in subsequent runs, reusing cached results from previous runs.

    def get_state_type(self) -> Type[DocumentSummarizationState]:
        """Get the type of the workflow state."""
        return DocumentSummarizationState

    def get_config_type(self) -> Type[DocumentSummarizationWorkflowConfig]:
        """Get the type of the workflow config."""
        return DocumentSummarizationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_document_summarization_graph()

    async def create_initial_state(
        self,
        config: DocumentSummarizationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> DocumentSummarizationState:
        """Create and return the initial state of the workflow."""

        return DocumentSummarizationState(
            type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
            main_file_id=get_main_file_id(existing_states),
            supporting_file_ids=get_supporting_file_ids(existing_states),
            config=config,
        )

    def convert_state_to_issues(
        self, state: DocumentSummarizationState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        # Document summarization doesn't produce issues
        return []
