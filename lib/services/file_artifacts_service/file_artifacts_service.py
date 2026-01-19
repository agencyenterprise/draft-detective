import logging
from typing import TYPE_CHECKING, cast

from lib.models.file import FileRole
from lib.services.file import FileDocument
from lib.services.files import (
    get_file_by_id,
    get_files_by_project_id,
    load_file_document,
)
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.models import WorkflowRunType

if TYPE_CHECKING:
    from lib.agents.document_summarizer import DocumentSummary
    from lib.models.bibliography_item import BibliographyItem
    from lib.models.footnote_item import FootnoteItem
    from lib.workflows.chunk_utils import AnalyzedChunk
    from lib.workflows.document_processing.state import DocumentProcessingState
    from lib.workflows.footnote_extraction.state import FootnoteExtractionState
    from lib.workflows.reference_extraction.state import ReferenceExtractionState
    from lib.workflows.types import WorkflowState

logger = logging.getLogger(__name__)


class FileArtifactsService(FileArtifactsServiceType):
    """Accesses file artifacts produced by workflow runs for a given project.

    Loads artifacts from the database cache when available and falls back to
    workflow checkpointer state when not.
    """

    def __init__(self, project_id: str) -> None:
        """Create a service instance bound to a project."""
        self.project_id = project_id

    async def _get_state_by_type(self, run_type: WorkflowRunType) -> "WorkflowState":
        """Return the workflow state for a given workflow run type."""
        from lib.services.workflow_runs import (
            get_project_workflow_run_by_type,
            get_workflow_run_state_by_thread_id,
        )

        workflow_run = await get_project_workflow_run_by_type(self.project_id, run_type)
        if not workflow_run:
            raise ValueError(
                f"No workflow run found for type {run_type} and project {self.project_id}"
            )

        state = await get_workflow_run_state_by_thread_id(
            workflow_run.langgraph_thread_id, run_type
        )
        if not state:
            raise ValueError(
                f"No state found for type {run_type} and project {self.project_id}"
            )

        return state

    async def _try_load(
        self,
        what: str,
        loader,
    ):
        """Run a loader and return its value, logging exceptions at debug level."""
        try:
            return await loader()
        except Exception as exc:  # keep broad: cache layer shouldn't break workflows
            logger.debug("Could not load %s from DB: %s", what, exc)
            return None

    async def get_file_document(self, file_id: str) -> FileDocument:
        """Return the file document for the given file id.

        Prefers DB cached markdown artifacts and falls back to workflow state.
        """
        file_doc = await self._try_load(
            f"file document {file_id}",
            lambda: self._get_file_document_from_db(file_id),
        )
        if file_doc is not None:
            return file_doc

        return await self._get_file_document_from_state(file_id)

    async def _get_file_document_from_db(self, file_id: str) -> FileDocument | None:
        """Return FileDocument from DB cached artifacts when available."""
        file = await get_file_by_id(file_id)
        if not file.has_cached_markdown:
            return None
        return await load_file_document(file, use_cached_artifacts=True)

    async def _get_file_document_from_state(self, file_id: str) -> FileDocument:
        """Return FileDocument from the document processing workflow state."""
        state = cast(
            "DocumentProcessingState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING),
        )

        if state.file.file_id == file_id:
            return state.file

        for supporting_file in state.supporting_files or []:
            if supporting_file.file_id == file_id:
                return supporting_file

        raise ValueError(
            f"No file document found with id {file_id} for project {self.project_id}"
        )

    async def _load_project_files(self):
        """Return all project files from DB (or None if DB read fails)."""
        return await self._try_load(
            f"project files for {self.project_id}",
            lambda: get_files_by_project_id(self.project_id),
        )

    async def get_main_file(self) -> FileDocument:
        """Return the project's main file.

        Prefers DB cached markdown artifacts and falls back to workflow state.
        """
        project_files = await self._load_project_files()
        if project_files:
            main_file = next(
                (f for f in project_files if f.role == FileRole.MAIN), None
            )
            if main_file and main_file.has_cached_markdown:
                logger.debug(
                    "Loaded main file from DB cache for project %s", self.project_id
                )
                return await load_file_document(main_file, use_cached_artifacts=True)

        state = cast(
            "DocumentProcessingState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING),
        )
        return state.file

    async def get_supporting_files(self) -> list[FileDocument]:
        """Return the project's supporting files.

        Prefers DB cached markdown artifacts when *all* supporting files are cached;
        otherwise falls back to workflow state.
        """
        project_files = await self._load_project_files()
        if project_files:
            supporting = [f for f in project_files if f.role == FileRole.SUPPORT]
            if supporting and all(f.has_cached_markdown for f in supporting):
                logger.debug(
                    "Loaded %d supporting files from DB cache for project %s",
                    len(supporting),
                    self.project_id,
                )
                return [
                    await load_file_document(f, use_cached_artifacts=True)
                    for f in supporting
                ]

        state = cast(
            "DocumentProcessingState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING),
        )
        return state.supporting_files or []

    async def get_document_summary(self, file_id: str) -> "DocumentSummary":
        """Return the document summary for a file.

        Prefers DB cached summary and falls back to workflow state.
        """
        from lib.agents.document_summarizer import DocumentSummary

        summary = await self._try_load(
            f"summary for file {file_id}",
            lambda: self._get_document_summary_from_db(file_id, DocumentSummary),
        )
        if summary is not None:
            return summary

        return await self._get_summary_from_state(file_id)

    async def _get_document_summary_from_db(self, file_id: str, summary_cls):
        """Return DocumentSummary from DB cached summary when available."""
        file = await get_file_by_id(file_id)
        if not file.has_cached_summary:
            return None
        logger.debug("Loaded summary for file %s from DB cache", file_id)
        return summary_cls(**file.summary)

    async def _get_summary_from_state(self, file_id: str) -> "DocumentSummary":
        """Return DocumentSummary from the document processing workflow state."""
        state = cast(
            "DocumentProcessingState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING),
        )

        if state.file.file_id == file_id:
            return state.main_document_summary

        for idx, f in enumerate(state.supporting_files or []):
            if f.file_id == file_id:
                return state.supporting_documents_summaries[idx]

        raise ValueError(
            f"No document summary found with id {file_id} for project {self.project_id}"
        )

    async def get_references(self) -> list["BibliographyItem"]:
        """Return bibliography references from the reference extraction workflow."""
        state = cast(
            "ReferenceExtractionState",
            await self._get_state_by_type(WorkflowRunType.REFERENCE_EXTRACTION),
        )
        return state.references

    async def get_chunks(self) -> list["AnalyzedChunk"]:
        """Return analyzed chunks built from all available workflow states."""
        from lib.services.workflow_runs import get_project_workflow_runs
        from lib.workflows.chunk_utils import build_analyzed_chunks

        workflow_runs = await get_project_workflow_runs(
            self.project_id, include_internal=True
        )
        states: list["WorkflowState"] = [
            run.state for run in workflow_runs if run.state is not None
        ]
        return build_analyzed_chunks(states)

    async def get_footnotes(self) -> list["FootnoteItem"]:
        """Return footnotes from the footnote extraction workflow."""
        state = cast(
            "FootnoteExtractionState",
            await self._get_state_by_type(WorkflowRunType.FOOTNOTE_EXTRACTION),
        )
        return state.footnotes
