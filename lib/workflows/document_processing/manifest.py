from typing import List, Type

from langgraph.graph import StateGraph

from lib.models.file import FileRole
from lib.workflows.document_processing.graph import build_document_processing_graph
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState


class DocumentProcessingManifest(
    WorkflowManifest[DocumentProcessingState, DocumentProcessingWorkflowConfig]
):
    type = WorkflowRunType.DOCUMENT_PROCESSING
    name = "Document Processing"
    description = "Convert documents to markdown and split into chunks"
    needs_web_search = False
    can_be_triggered_by_user = (
        False  # This is a dependency workflow, not directly triggered
    )
    is_internal = True
    optional_dependencies = [
        # This is a hack to make doc processing wait for reference downloader to complete, so we can process the files
        # that were downloaded by reference downloader
        WorkflowRunType.REFERENCE_DOWNLOADER,
    ]

    def get_state_type(self) -> Type[DocumentProcessingState]:
        """Get the type of the workflow state."""
        return DocumentProcessingState

    def get_config_type(self) -> Type[DocumentProcessingWorkflowConfig]:
        """Get the type of the workflow config."""
        return DocumentProcessingWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_document_processing_graph()

    async def create_initial_state(
        self,
        config: DocumentProcessingWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> DocumentProcessingState:
        """Create and return the initial state of the workflow."""

        from lib.services.files import get_files_by_project_id, load_file_document

        assert config.project_id is not None, "Missing project_id in config"

        project_files = await get_files_by_project_id(config.project_id)
        main_file = next(
            (file for file in project_files if file.role == FileRole.MAIN),
            None,
        )
        supporting_files = [
            file for file in project_files if file.role == FileRole.SUPPORT
        ]
        assert main_file is not None, "No main file found for project"
        main_file_document = await load_file_document(main_file)
        assert main_file_document is not None, "Failed to load main file"
        supporting_file_documents = [
            await load_file_document(file) for file in supporting_files
        ]

        return DocumentProcessingState(
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            file=main_file_document,
            supporting_files=supporting_file_documents,
            config=config,
        )

    def convert_state_to_issues(
        self, state: DocumentProcessingState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        # Document processing doesn't produce issues
        return []
