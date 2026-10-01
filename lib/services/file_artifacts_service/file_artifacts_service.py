import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast, Callable, Awaitable, Any

from deepagents.backends.utils import create_file_data

from lib.models.file import File, FileRole
from lib.services.file import FileDocument, create_file_document_from_path
from lib.services.files import (
    get_file_by_id,
    get_files_by_project_id,
    load_file_document,
)
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.skills import strip_interactive_only
from lib.workflows.models import WorkflowRunType

if TYPE_CHECKING:
    from lib.models.bibliography_item import BibliographyItem
    from lib.workflows.document_processing.state import DocumentProcessingState
    from lib.workflows.document_summarization.state import (
        DocumentSummarizationState,
        FileSummary,
    )
    from lib.workflows.reference_extraction.state import (
        ExtractedReference,
        ReferenceExtractionState,
    )
    from lib.workflows.reference_file_matching.state import ReferenceFileMatchingState
    from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)

# Where each revision-scoped memo role is mounted under `/revisions/<n>/`.
_MEMO_FOLDERS: dict[FileRole, str] = {
    FileRole.REVIEWER_MEMO: "reviewer-memos",
    FileRole.RESPONSE_MEMO: "response-memos",
}


class FileArtifactsService(FileArtifactsServiceType):
    """Accesses file artifacts produced by workflow runs for a given project.

    Loads artifacts from the database cache when available and falls back to
    the workflow run's persisted state (state_json) when not.
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
            read_workflow_run_state,
        )

        workflow_run = await get_project_workflow_run_by_type(
            self.project_id, run_type, revision=self.revision, include_state=True
        )
        if not workflow_run:
            if raise_exception:
                raise ValueError(
                    f"No workflow run found for type {run_type} and project {self.project_id}"
                )
            return None

        state = await read_workflow_run_state(workflow_run)
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

    async def _load_main_files(self, revision: int | None = None):
        """Return the revision's MAIN files from DB (or None if DB read fails).

        Defaults to the service's own revision; pass ``revision`` to read a
        different (e.g. earlier) revision's files.
        """
        rev = revision if revision is not None else self.revision
        return await self._try_load(
            f"main files for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id, roles=[FileRole.MAIN], revision=rev
            ),
        )

    async def _load_file_document_with_markdown(self, file: File) -> FileDocument:
        """Load a File row into a FileDocument, converting markdown on demand.

        Uses cached markdown when present, otherwise converts from disk.
        """
        if file.markdown is not None:
            return await load_file_document(file, use_cached_artifacts=True)
        return await create_file_document_from_path(
            file_path=file.file_path,
            file_id=str(file.id),
            file_type=file.file_type,
            original_file_name=file.file_name,
            original_file_path=file.original_file_path,
            markdown_convert=True,
        )

    async def get_main_file(self, revision: int | None = None) -> FileDocument:
        """Return the project's main file.

        Defaults to the service's revision and falls back to the document
        processing state. When an explicit ``revision`` is given (e.g. an
        earlier reviewed revision), the file is read from the DB and its
        markdown converted on demand — the state fallback only applies to the
        current revision.
        """
        rev = revision if revision is not None else self.revision
        main_files = await self._load_main_files(rev)
        main_file = main_files[0] if main_files else None

        if revision is not None:
            if main_file is None:
                raise ValueError(
                    f"No main file found for revision {rev} in project {self.project_id}"
                )
            return await self._load_file_document_with_markdown(main_file)

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

    async def get_project_files(
        self, roles: list[FileRole], revision: int | None = None
    ) -> list[FileDocument]:
        """Return the project's files for the given roles, with markdown content.

        Defaults to the service's revision; pass ``revision`` to read a
        different revision's files. Prefers DB cached markdown and converts a
        file's markdown on demand when it has not been cached yet (e.g. reviewer
        memos, which are not processed by the document pipeline).
        """
        rev = revision if revision is not None else self.revision
        role_labels = ", ".join(r.value for r in roles)
        files = await self._try_load(
            f"project files ({role_labels}) for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id,
                roles=roles,
                revision=rev,
            ),
        )
        if not files:
            return []

        documents: list[FileDocument] = []
        for file in files:
            documents.append(await self._load_file_document_with_markdown(file))
        return documents

    async def get_latest_reviewer_memo_revision(self) -> int | None:
        """Return the highest revision that has reviewer memos, or None.

        Reviewer memos are scoped to the revision they reviewed; this resolves
        the "reviewed revision" the review workflows operate on.
        """
        files = await self._try_load(
            f"reviewer memo revisions for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id, roles=[FileRole.REVIEWER_MEMO]
            ),
        )
        if not files:
            return None
        revisions = [f.revision for f in files if f.revision is not None]
        return max(revisions) if revisions else None

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
            supporting_files = await self.get_project_files([FileRole.SUPPORT])
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
                    reference_id=ref.id,
                )
            )

        return references

    async def get_deepagent_backend_files(
        self,
        include_skills: bool = True,
    ) -> dict[str, Any]:
        """Return the full project file tree for the DeepAgent backend.

        Layout (always the same shape):

        - ``/main.md`` — the current revision's main document
        - ``/supporting/<id>.md`` — supporting documents (shared across revisions)
        - ``/revisions/<n>/main.md`` — the main document of every revision
        - ``/revisions/<n>/reviewer-memos/<id>.md`` — reviewer memos, always
          grouped under the revision they reviewed
        - ``/revisions/<n>/response-memos/<id>.md`` — the author's response
          memos, grouped under the revised draft they describe

        Memos live only under their revision's folder. The agent navigates
        this tree; workflows tell it which paths to read.
        """
        main_file = await self.get_main_file()
        files: dict[str, Any] = {"/main.md": create_file_data(main_file.markdown)}

        all_files = await self._try_load(
            f"all files for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id,
                roles=[
                    FileRole.MAIN,
                    FileRole.SUPPORT,
                    FileRole.REVIEWER_MEMO,
                    FileRole.RESPONSE_MEMO,
                ],
            ),
        )
        for file in all_files or []:
            if file.role == FileRole.SUPPORT:
                doc = await self._load_file_document_with_markdown(file)
                files[f"/supporting/{doc.file_id}.md"] = create_file_data(doc.markdown)
            elif file.role == FileRole.MAIN and file.revision is not None:
                doc = await self._load_file_document_with_markdown(file)
                files[f"/revisions/{file.revision}/main.md"] = create_file_data(
                    doc.markdown
                )
            elif file.role in _MEMO_FOLDERS and file.revision is not None:
                doc = await self._load_file_document_with_markdown(file)
                folder = _MEMO_FOLDERS[file.role]
                files[f"/revisions/{file.revision}/{folder}/{doc.file_id}.md"] = (
                    create_file_data(doc.markdown)
                )

        if include_skills:
            project_root = Path(__file__).parents[3]
            skills_dir = project_root / "skills"
            for skill_file in sorted(skills_dir.rglob("*")):
                if skill_file.is_file():
                    virtual_path = "/" + skill_file.relative_to(project_root).as_posix()
                    # Interactive-only sections (e.g. asking the user for
                    # web-search consent) are for agents driven by a user; a
                    # backend run has its consent already and nobody to ask.
                    files[virtual_path] = create_file_data(
                        strip_interactive_only(skill_file.read_text())
                    )

        return files
