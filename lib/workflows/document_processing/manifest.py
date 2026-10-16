import builtins
import logging

from langgraph.graph import StateGraph

from lib.models.file import FileRole
from lib.services.files.document import FileDocument
from lib.services.files.service import get_files_by_project_id, load_file_document
from lib.workflows.document_processing.graph import build_document_processing_graph
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)


class DocumentProcessingManifest(
    WorkflowManifest[DocumentProcessingState, DocumentProcessingWorkflowConfig]
):
    type = WorkflowRunType.DOCUMENT_PROCESSING
    name = "Markdown Conversion"
    description = "Convert documents to markdown"
    needs_web_search = False
    is_internal = True
    always_run = True  # Always run document processing to ensure new files are processed. The workflow processes only new files in subsequent runs, reusing cached results from previous runs.

    def get_state_type(self) -> builtins.type[DocumentProcessingState]:
        """Get the type of the workflow state."""
        return DocumentProcessingState

    def get_config_type(self) -> builtins.type[DocumentProcessingWorkflowConfig]:
        """Get the type of the workflow config."""
        return DocumentProcessingWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_document_processing_graph()

    async def create_initial_state(
        self,
        config: DocumentProcessingWorkflowConfig,
        existing_states: list[WorkflowState],
        revision: int,
        prior_self_state: DocumentProcessingState | None = None,
    ) -> DocumentProcessingState:
        """Create and return the initial state of the workflow."""
        project_files = await get_files_by_project_id(
            config.project_id,
            roles=[
                FileRole.MAIN,
                FileRole.SUPPORT,
            ],
            revision=revision,
        )
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

        # Supporting docs are loaded tolerantly: a file that fails to load is
        # skipped and logged rather than aborting the workflow.
        supporting_file_documents: list[FileDocument] = []
        for file in supporting_files:
            try:
                supporting_file_documents.append(await load_file_document(file))
            except Exception as exc:
                logger.warning(
                    "Skipping supporting file %s (%s) — failed to load: %s",
                    file.file_name,
                    file.id,
                    exc,
                )

        return DocumentProcessingState(
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            file=main_file_document,
            supporting_files=supporting_file_documents,
            config=config,
        )

    def convert_state_to_issues(
        self, state: DocumentProcessingState, other_states: list[WorkflowState]
    ) -> list[DocumentIssue]:
        # Document processing doesn't produce issues
        return []
