import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, overload

from deepagents.backends.utils import create_file_data

from lib.models.bibliography_item import BibliographyItem
from lib.models.file import File, FileRole
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
    LoadedDocuments,
    UnreadableDocument,
)
from lib.services.files.conversion import convert_file_document_to_markdown
from lib.services.files.document import FileDocument
from lib.services.files.service import (
    get_file_by_id,
    get_files_by_project_id,
    load_file_document,
    update_file_artifacts,
)
from lib.services.workflow_runs.service import (
    get_project_workflow_run_by_type,
    read_workflow_run_state,
)
from lib.skills import skill_backend_files
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    FileSummary,
)
from lib.workflows.models import BaseWorkflowState
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionState,
)
from lib.workflows.reference_file_matching.state import ReferenceFileMatchingState
from lib.workflows.util import as_state_type, run_type_of

logger = logging.getLogger(__name__)


# Every role a person uploads, as opposed to the files the app derives.
_UPLOADED_ROLES = [
    FileRole.MAIN,
    FileRole.SUPPORT,
    FileRole.REVIEWER_MEMO,
    FileRole.RESPONSE_MEMO,
    FileRole.REVIEW_INPUT,
]


def _as_uuids(file_ids: list[str]) -> list[uuid.UUID]:
    """The ids that parse as UUIDs; any other cannot name a file, so it drops out."""
    parsed: list[uuid.UUID] = []
    for file_id in file_ids:
        try:
            parsed.append(uuid.UUID(file_id))
        except ValueError:
            continue
    return parsed


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

    @overload
    async def _get_state[StateType: BaseWorkflowState](
        self,
        state_type: type[StateType],
        raise_exception: Literal[True] = True,
    ) -> StateType: ...

    @overload
    async def _get_state[StateType: BaseWorkflowState](
        self,
        state_type: type[StateType],
        raise_exception: Literal[False],
    ) -> StateType | None: ...

    async def _get_state[StateType: BaseWorkflowState](
        self,
        state_type: type[StateType],
        raise_exception: bool = True,
    ) -> StateType | None:
        """Retrieve the state of the run type a state class pins.

        Args:
            state_type: The state class, which names the run type to look up.
            raise_exception: Whether to raise an exception if no workflow run or state is found.

        Returns:
            The workflow state for the specified workflow run type.

        Raises:
            ValueError: If no workflow run or state is found for the given type
                and project ID.
        """
        run_type = run_type_of(state_type)
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

        return as_state_type(state, state_type) if state is not None else None

    async def _try_load[T](
        self,
        what: str,
        loader: Callable[[], Awaitable[T]],
    ) -> T | None:
        """Run a loader and return its value, or None (with a warning) if it raises."""
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
        state = await self._get_state(DocumentProcessingState)

        if state.file.file_id == file_id:
            return state.file

        for supporting_file in state.supporting_files or []:
            if supporting_file.file_id == file_id:
                return supporting_file

        raise ValueError(
            f"No file document found with id {file_id} for project {self.project_id}"
        )

    async def _load_main_files(self, revision: int | None = None) -> list[File] | None:
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

        Uses cached markdown when present. Otherwise the file has not been
        through document processing, which only converts the current
        revision's files, or a Review Assistant document, which it never reads.
        It is then converted the way document processing would (legacy ``.doc``
        included, with the converter its role calls for) and cached, so the
        next run reads it from the DB.
        """
        if file.markdown is not None:
            return await load_file_document(file, use_cached_artifacts=True)

        document = await load_file_document(file, use_cached_artifacts=False)
        converted = await convert_file_document_to_markdown(document, role=file.role)
        if converted.markdown:
            await update_file_artifacts(
                file_id=converted.file_id, markdown=converted.markdown
            )
        return converted

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

        state = await self._get_state(DocumentProcessingState)
        return state.file

    async def get_project_files(self, roles: list[FileRole]) -> list[FileDocument]:
        """Return the project's files for the given roles, with markdown content.

        Reads the service's revision. Prefers DB cached markdown and converts a
        file's markdown on demand when it has not been cached yet.
        """
        role_labels = ", ".join(r.value for r in roles)
        files = await self._try_load(
            f"project files ({role_labels}) for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id,
                roles=roles,
                revision=self.revision,
            ),
        )
        if not files:
            return []

        documents: list[FileDocument] = []
        for file in files:
            documents.append(await self._load_file_document_with_markdown(file))
        return documents

    async def get_file_summary(self, file_id: str) -> FileSummary:
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
        summary = await self._try_load(
            f"summary for file {file_id}",
            lambda: self._get_file_summary_from_db(file_id),
        )
        if summary is not None:
            return summary

        return await self._get_summary_from_state(file_id)

    async def _get_file_summary_from_db(self, file_id: str) -> FileSummary | None:
        """Return FileSummary from DB cached summary when available."""
        file = await get_file_by_id(file_id)
        if not file.has_cached_summary or file.summary is None:
            return None
        logger.debug("Loaded summary for file %s from DB cache", file_id)
        return FileSummary(file_id=file_id, **file.summary)

    async def _get_summary_from_state(self, file_id: str) -> FileSummary:
        """Return FileSummary from the document summarization workflow state."""
        state = await self._get_state(DocumentSummarizationState)

        summary = next(
            (s for s in state.summaries if s.file_id == file_id),
            None,
        )
        if summary is not None:
            return summary

        raise ValueError(
            f"No file summary found with id {file_id} for project {self.project_id}"
        )

    async def get_extracted_references(self) -> list[ExtractedReference]:
        """Retrieve raw extracted references from the reference extraction workflow.

        Returns:
            A list of ExtractedReference objects with id and text.

        Raises:
            ValueError: If no reference extraction workflow run or state is found
                for the project.
        """
        state = await self._get_state(ReferenceExtractionState)
        return state.extracted_references

    async def get_references(self) -> list[BibliographyItem]:
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
        # Get extracted references (required)
        extraction_state = await self._get_state(ReferenceExtractionState)
        extracted_refs = extraction_state.extracted_references

        if not extracted_refs:
            return []

        # Try to get file matching state (optional)
        matching_state = await self._get_state(
            ReferenceFileMatchingState,
            raise_exception=False,
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

        The agent navigates this tree; workflows tell it which paths to read.
        """
        main_file = await self.get_main_file()
        files: dict[str, Any] = {"/main.md": create_file_data(main_file.markdown)}

        all_files = await self._try_load(
            f"all files for {self.project_id}",
            lambda: get_files_by_project_id(
                self.project_id,
                roles=[FileRole.MAIN, FileRole.SUPPORT],
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

        if include_skills:
            files.update(skill_backend_files())

        return files

    async def get_file_documents(self, file_ids: list[str]) -> LoadedDocuments:
        """Load the project's files with these ids, markdown included.

        Ids that are not this project's uploaded documents load nothing, so a
        caller cannot reach another project's file by naming it; they are
        reported as unreadable, since the request named them. A file that
        fails to load or convert is reported rather than raised, so one bad
        upload does not cost the caller the rest. Order follows ``file_ids``.
        """
        files = await get_files_by_project_id(
            self.project_id, roles=_UPLOADED_ROLES, file_ids=_as_uuids(file_ids)
        )
        by_id = {str(file.id): file for file in files}
        loaded = LoadedDocuments(documents=[])
        for file_id in file_ids:
            file = by_id.get(file_id)
            if file is None:
                # The request was checked when it started, so a missing file was
                # deleted since. Say so, rather than report without it.
                loaded.unreadable.append(
                    UnreadableDocument(
                        file_id=file_id,
                        file_name="a selected document",
                        reason="it was deleted from the project.",
                    )
                )
                continue
            try:
                loaded.documents.append(
                    await self._load_file_document_with_markdown(file)
                )
            except Exception as error:
                logger.warning(
                    "Could not read %s (%s): %s", file.file_name, file_id, error
                )
                loaded.unreadable.append(
                    UnreadableDocument(
                        file_id=file_id, file_name=file.file_name, reason=str(error)
                    )
                )
        return loaded
