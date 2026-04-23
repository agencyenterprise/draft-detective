import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast, Callable, Awaitable, Any
import asyncio

from deepagents.backends.utils import create_file_data

from lib.models.file import FileRole
from lib.services.file import FileDocument
from lib.services.files import (
    get_file_by_id,
    get_files_by_project_id,
    load_file_document,
)
from lib.services.file_artifacts_service.file_artifacts_service_type import FileArtifactsServiceType
from lib.workflows.models import WorkflowRunType

if TYPE_CHECKING:
    from lib.models.bibliography_item import BibliographyItem
    from lib.models.footnote_item import FootnoteItem
    from lib.workflows.chunk_utils import AnalyzedChunk
    from lib.workflows.document_processing.state import DocumentProcessingState
    from lib.workflows.document_summarization.state import (
        DocumentSummarizationState,
        FileSummary,
    )
    from lib.workflows.footnote_extraction.state import FootnoteExtractionState
    from lib.workflows.reference_extraction.state import (
        ExtractedReference,
        ReferenceExtractionState,
    )
    from lib.workflows.reference_file_matching.state import ReferenceFileMatchingState
    from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)


class FileArtifactsService(FileArtifactsServiceType):
    """Accesses file artifacts produced by workflow runs for a given project.

    Loads artifacts from the database cache when available and falls back to
    workflow checkpointer state when not.
    """

    def __init__(self, project_id: str, revision: int) -> None:
        """Initialize the service with a project ID and revision.

        Args:
            project_id: The unique identifier for the project whose artifacts
                should be accessed.
            revision: The project revision to scope lookups to.
        """
        self.project_id = project_id
        self.revision = revision

    async def _get_state_by_type(
        self, run_type: WorkflowRunType, raise_exception: bool = True
    ) -> Optional["WorkflowState"]:
        """Retrieve workflow state for a specific workflow run type.

        Args:
            run_type: The type of workflow run to retrieve state for.
            raise_exception: Whether to raise an exception if no workflow run or state is found.

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

        workflow_run = await get_project_workflow_run_by_type(
            self.project_id, run_type, revision=self.revision
        )
        if not workflow_run:
            if raise_exception:
                raise ValueError(
                    f"No workflow run found for type {run_type} and project {self.project_id}"
                )
            return None

        state = await get_workflow_run_state_by_thread_id(
            workflow_run.langgraph_thread_id, run_type
        )
        if not state and raise_exception:
            raise ValueError(
                f"No state found for type {run_type} and project {self.project_id}"
            )

        return state

    async def _try_load(
        self,
        what: str,
        loader: Callable[[], Awaitable[Any]],
    ):
        """Run a loader and return its value, logging exceptions at debug level."""
        try:
            return await loader()
        except Exception as exc:
            logger.warning("Could not load %s from DB: %s", what, exc)
            return None

    async def get_file_document(self, file_id: str) -> FileDocument:
        """Retrieve the file document for a file by its ID.

        Args:
            file_id: The unique identifier of the file to retrieve the document for.

        Returns:
            The file document for the requested file.

        Raises:
            ValueError: If no file document is found for the given file ID.
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
            lambda: get_files_by_project_id(self.project_id, revision=self.revision),
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

                return await asyncio.gather(
                    *[
                        load_file_document(f, use_cached_artifacts=True)
                        for f in supporting
                    ]
                )

        state = cast(
            "DocumentProcessingState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING),
        )
        return state.supporting_files or []

    async def get_file_summary(self, file_id: str) -> "FileSummary":
        """Retrieve the file summary for a file by its ID.
        Prefers DB cached summaries and falls back to workflow state.

        Args:
            file_id: The unique identifier of the file to retrieve the summary for.

        Returns:
            The file summary for the requested file.

        Raises:
            ValueError: If no file summary with the given file ID is found
                in the project's document summarization workflow state.
        """
        from lib.workflows.document_summarization.state import FileSummary

        summary = await self._try_load(
            f"summary for file {file_id}",
            lambda: self._get_file_summary_from_db(file_id, FileSummary),
        )
        if summary is not None:
            return summary

        return await self._get_summary_from_state(file_id)

    async def _get_file_summary_from_db(
        self, file_id: str, summary_cls: type["FileSummary"]
    ) -> "FileSummary | None":
        """Return FileSummary from DB cached summary when available."""
        file = await get_file_by_id(file_id)
        if not file.has_cached_summary or file.summary is None:
            return None
        logger.debug("Loaded summary for file %s from DB cache", file_id)
        return summary_cls(file_id=file_id, **file.summary)

    async def _get_summary_from_state(self, file_id: str) -> "FileSummary":
        """Return FileSummary from the document summarization workflow state."""
        state = cast(
            "DocumentSummarizationState",
            await self._get_state_by_type(WorkflowRunType.DOCUMENT_SUMMARIZATION),
        )

        summary = next(
            (s for s in state.summaries if s.file_id == file_id),
            None,
        )
        if summary is not None:
            return summary

        raise ValueError(
            f"No file summary found with id {file_id} for project {self.project_id}"
        )

    async def get_extracted_references(self) -> list["ExtractedReference"]:
        """Retrieve raw extracted references from the reference extraction workflow.

        Returns:
            A list of ExtractedReference objects with id and text.

        Raises:
            ValueError: If no reference extraction workflow run or state is found
                for the project.
        """
        state = cast(
            "ReferenceExtractionState",
            await self._get_state_by_type(WorkflowRunType.REFERENCE_EXTRACTION),
        )
        return state.extracted_references

    async def get_references(self) -> list["BibliographyItem"]:
        """Retrieve extracted references as BibliographyItem objects.

        Composes BibliographyItem objects from:
        1. ReferenceExtractionState - provides extracted references (id + text)
        2. ReferenceFileMatchingState - provides file matches (may not exist)

        Returns:
            A list of BibliographyItem objects with file matching info if available.

        Raises:
            ValueError: If no reference extraction workflow run or state is found
                for the project.
        """
        from lib.models.bibliography_item import BibliographyItem

        # Get extracted references (required)
        extraction_state = cast(
            "ReferenceExtractionState",
            await self._get_state_by_type(WorkflowRunType.REFERENCE_EXTRACTION),
        )
        extracted_refs = extraction_state.extracted_references

        if not extracted_refs:
            return []

        # Try to get file matching state (optional)
        matching_state = cast(
            Optional["ReferenceFileMatchingState"],
            await self._get_state_by_type(
                WorkflowRunType.REFERENCE_FILE_MATCHING, raise_exception=False
            ),
        )

        # Build lookup of reference_id -> file info
        ref_to_file: dict[str, str] = {}
        file_names: dict[str, str] = {}
        file_indices: dict[str, int] = {}

        if matching_state is not None:
            for match in matching_state.matches:
                ref_to_file[match.reference_id] = match.file_id

            # Load file names for matched files
            supporting_files = await self.get_supporting_files()
            for idx, f in enumerate(supporting_files):
                file_names[f.file_id] = f.file_name
                file_indices[f.file_id] = idx + 1  # 1-based index

        # Build BibliographyItem objects
        references: list[BibliographyItem] = []
        for ref in extracted_refs:
            file_id = ref_to_file.get(ref.id)
            has_match = file_id is not None

            references.append(
                BibliographyItem(
                    text=ref.text,
                    has_associated_supporting_document=has_match,
                    index_of_associated_supporting_document=(
                        file_indices.get(file_id, -1) if file_id else -1
                    ),
                    name_of_associated_supporting_document=(
                        file_names.get(file_id, "") if file_id else ""
                    ),
                    file_id=file_id,
                )
            )

        return references

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

        workflow_runs = await get_project_workflow_runs(
            self.project_id, revision=self.revision, include_internal=True
        )
        states: list["WorkflowState"] = [
            run.state for run in workflow_runs if run.state is not None
        ]
        return build_analyzed_chunks(states)

    async def get_footnotes(self) -> list["FootnoteItem"]:
        """Retrieve extracted footnotes from the footnote extraction workflow.

        Returns:
            A list of extracted footnote items from the footnote extraction
            workflow state.

        Raises:
            ValueError: If no footnote extraction workflow run or state is found
                for the project.
        """

        state = cast(
            "FootnoteExtractionState",
            await self._get_state_by_type(WorkflowRunType.FOOTNOTE_EXTRACTION),
        )
        return state.footnotes

    async def get_deepagent_backend_files(
        self,
        include_supporting_files: bool = True,
        include_skills: bool = True,
    ) -> dict[str, Any]:
        """Return the files in a format suitable for the DeepAgent backend."""

        main_file = await self.get_main_file()
        supporting_files = (
            await self.get_supporting_files() if include_supporting_files else []
        )

        files: dict[str, Any] = {
            "/main.md": create_file_data(main_file.markdown),
            **{
                f"/supporting/{f.file_id}.md": create_file_data(f.markdown)
                for f in supporting_files
            },
        }

        if include_skills:
            project_root = Path(__file__).parents[3]
            skills_dir = project_root / "skills"
            for skill_file in sorted(skills_dir.rglob("*")):
                if skill_file.is_file():
                    virtual_path = "/" + skill_file.relative_to(project_root).as_posix()
                    files[virtual_path] = create_file_data(skill_file.read_text())

        return files
