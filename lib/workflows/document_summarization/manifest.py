"""Manifest for document summarization workflow."""

import builtins

from langgraph.graph import StateGraph

from lib.services.files.service import (
    get_main_file_id,
    get_processed_supporting_file_ids,
)
from lib.workflows.document_summarization.graph import (
    build_document_summarization_graph,
)
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    DocumentSummarizationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState


class DocumentSummarizationManifest(
    WorkflowManifest[DocumentSummarizationState, DocumentSummarizationWorkflowConfig]
):
    type = WorkflowRunType.DOCUMENT_SUMMARIZATION
    name = "Document Summarization"
    description = "Summarize the main document and supporting documents"
    needs_web_search = False
    is_internal = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    always_run = True  # Always run document summarization to ensure new files are summarized. The workflow summarizes only new files in subsequent runs, reusing cached results from previous runs.

    def get_state_type(self) -> builtins.type[DocumentSummarizationState]:
        """Get the type of the workflow state."""
        return DocumentSummarizationState

    def get_config_type(self) -> builtins.type[DocumentSummarizationWorkflowConfig]:
        """Get the type of the workflow config."""
        return DocumentSummarizationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_document_summarization_graph()

    async def create_initial_state(
        self,
        config: DocumentSummarizationWorkflowConfig,
        existing_states: list[WorkflowState],
        revision: int,
        prior_self_state: DocumentSummarizationState | None = None,
    ) -> DocumentSummarizationState:
        """Create and return the initial state of the workflow.

        Seeds summaries from the prior run's state so already-computed
        per-file summaries carry forward (the summarize node reuses them and
        only summarizes new files). Threads are no longer reused across runs,
        so this state is no longer inherited via the checkpointer.
        """
        summaries = prior_self_state.summaries if prior_self_state is not None else []
        return DocumentSummarizationState(
            type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
            main_file_id=await get_main_file_id(config.project_id, revision),
            supporting_file_ids=await get_processed_supporting_file_ids(
                config.project_id, revision
            ),
            config=config,
            summaries=summaries,
        )

    def convert_state_to_issues(
        self, state: DocumentSummarizationState, other_states: list[WorkflowState]
    ) -> list[DocumentIssue]:
        # Document summarization doesn't produce issues
        return []
