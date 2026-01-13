from typing import List, cast, TYPE_CHECKING

from lib.services.file import FileDocument

from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.models import WorkflowRunType

if TYPE_CHECKING:
    from lib.workflows.document_processing.state import DocumentProcessingState
    from lib.workflows.reference_extraction.state import ReferenceExtractionState
    from lib.workflows.claim_substantiation.state import AnalyzedChunk
    from lib.agents.document_summarizer import DocumentSummary
    from lib.models.bibliography_item import BibliographyItem
    from lib.workflows.types import WorkflowState


class FileArtifactsService(FileArtifactsServiceType):
    """Service for accessing file artifacts from workflow runs.

    This service provides access to file-related artifacts (markdown content,
    document summaries) stored in workflow state. It retrieves data from
    document processing workflow runs for a specific project.
    """

    def __init__(self, project_id: str):
        """Initialize the service with a project ID.

        Args:
            project_id: The unique identifier for the project whose artifacts
                should be accessed.
        """
        self.project_id = project_id

    async def _get_state_by_type(self, type: WorkflowRunType) -> "WorkflowState":
        """Retrieve workflow state for a specific workflow run type.

        Args:
            type: The type of workflow run to retrieve state for.

        Returns:
            The workflow state for the specified workflow run type.

        Raises:
            ValueError: If no workflow run or state is found for the given type
                and project ID.
        """
        from lib.services.workflow_runs import (
            get_project_workflow_run_by_type,
            get_workflow_run_state_by_thread_id,
        )

        workflow_run = await get_project_workflow_run_by_type(self.project_id, type)

        if not workflow_run:
            raise ValueError(
                f"No workflow run found for type {type} and project {self.project_id}"
            )

        state = await get_workflow_run_state_by_thread_id(
            workflow_run.langgraph_thread_id, type
        )

        if not state:
            raise ValueError(
                f"No state found for type {type} and project {self.project_id}"
            )

        return state

    async def get_file_document(self, file_id: str) -> FileDocument:
        """Retrieve the file document for a file by its ID.

        Args:
            file_id: The unique identifier of the file to retrieve the document for.

        Returns:
            The file document for the requested file.
        """
        doc_processing_state = await self._get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING
        )
        doc_processing_state = cast("DocumentProcessingState", doc_processing_state)

        if doc_processing_state.file.file_id == file_id:
            return doc_processing_state.file

        for supporting_file in doc_processing_state.supporting_files or []:
            if supporting_file.file_id == file_id:
                return supporting_file

        raise ValueError(
            f"No file document found with id {file_id} for project {self.project_id}"
        )

    async def get_main_file(self) -> FileDocument:
        """Retrieve the main file for the project."""
        doc_processing_state = await self._get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING
        )
        doc_processing_state = cast("DocumentProcessingState", doc_processing_state)
        return doc_processing_state.file

    async def get_supporting_files(self) -> list[FileDocument]:
        """Retrieve the supporting files for the project."""
        doc_processing_state = await self._get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING
        )
        doc_processing_state = cast("DocumentProcessingState", doc_processing_state)
        return doc_processing_state.supporting_files or []

    async def get_document_summary(self, file_id: str) -> "DocumentSummary":
        """Retrieve the document summary for a file by its ID.

        Args:
            file_id: The unique identifier of the file to retrieve the summary for.

        Returns:
            The document summary for the requested file.

        Raises:
            ValueError: If no document summary with the given file ID is found
                in the project's document processing workflow state.
        """
        doc_processing_state = await self._get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING
        )
        doc_processing_state = cast("DocumentProcessingState", doc_processing_state)

        if doc_processing_state.file.file_id == file_id:
            return doc_processing_state.main_document_summary

        file_index = next(
            (
                i
                for i, f in enumerate(doc_processing_state.supporting_files or [])
                if f.file_id == file_id
            ),
            None,
        )

        if file_index is not None:
            return doc_processing_state.supporting_documents_summaries[file_index]

        raise ValueError(
            f"No document summary found with id {file_id} for project {self.project_id}"
        )

    async def get_references(self) -> list["BibliographyItem"]:
        """Retrieve extracted references from the reference extraction workflow.

        Returns:
            A list of extracted bibliography items from the reference extraction
            workflow state.

        Raises:
            ValueError: If no reference extraction workflow run or state is found
                for the project.
        """
        ref_extraction_state = await self._get_state_by_type(
            WorkflowRunType.REFERENCE_EXTRACTION
        )
        ref_extraction_state = cast("ReferenceExtractionState", ref_extraction_state)

        return ref_extraction_state.references

    async def get_chunks(self) -> list["AnalyzedChunk"]:
        """Retrieve analyzed chunks from workflow states.

        Builds analyzed chunks by extracting chunks from document processing state
        and enriching them with claims, claim categories, and citations from their
        respective workflow states (claim extraction, citation detection).

        Returns:
            A list of analyzed chunks with all available analysis results.
            Returns empty list if document processing state is not found.

        Raises:
            ValueError: If no workflow runs are found for the project.
        """
        from lib.services.workflow_runs import get_project_workflow_runs
        from lib.workflows.chunk_utils import build_analyzed_chunks

        # Get all workflow runs including internal ones for dependency resolution
        workflow_runs = await get_project_workflow_runs(
            self.project_id, include_internal=True
        )

        # Extract states from workflow run details
        existing_states: list["WorkflowState"] = [
            run.state for run in workflow_runs if run.state is not None
        ]

        return build_analyzed_chunks(existing_states)
