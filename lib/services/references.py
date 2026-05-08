import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import List, Optional, Tuple, cast

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_runs import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    get_workflow_run_state_by_thread_id,
    persist_workflow_run_state,
)
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import WorkflowRunType
from langgraph.types import Overwrite

from lib.workflows.reference_downloader.state import ReferenceDownloaderState
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingState,
)
from lib.workflows.registry import create_graph

logger = logging.getLogger(__name__)


# Project-level locks to prevent race conditions on concurrent state updates
# Using LRU cache to limit memory usage - keeps most recently used locks
@lru_cache(maxsize=128)
def _get_project_lock(project_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific project (cached with LRU eviction)."""
    return asyncio.Lock()


@asynccontextmanager
async def _project_lock(project_id: str):
    """
    Acquire a lock for a specific project to prevent race conditions.

    This ensures that concurrent operations on the same project's reference
    state are serialized, while operations on different projects can proceed
    in parallel.
    """
    lock = _get_project_lock(project_id)
    async with lock:
        yield


async def _get_document_processing_workflow_state(project_id: str, revision: int):
    """Get the DocumentProcessing workflow state for a project."""
    from lib.workflows.document_processing.state import DocumentProcessingState

    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.DOCUMENT_PROCESSING, revision=revision
    )
    if run is None:
        return None

    state = await get_workflow_run_state_by_thread_id(
        run.langgraph_thread_id, WorkflowRunType.DOCUMENT_PROCESSING
    )
    return state


async def _get_file_matching_workflow_state(
    project_id: str,
    revision: int,
) -> Tuple[Optional[WorkflowRun], Optional[ReferenceFileMatchingState]]:
    """
    Get the ReferenceFileMatching workflow run and state for a project.

    If the workflow run exists but has no state, or if there's no workflow run,
    creates a new workflow run and constructs a default ReferenceFileMatchingState
    with empty matches using file information from the DocumentProcessing workflow.

    Args:
        project_id: The project ID

    Returns:
        Tuple of (workflow_run, state) or (None, None) if document processing
        state is not available to construct a default state
    """
    from lib.workflows.reference_file_matching.state import ReferenceFileMatchingConfig

    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.REFERENCE_FILE_MATCHING, revision=revision
    )

    state = None
    if run is not None:
        state = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, WorkflowRunType.REFERENCE_FILE_MATCHING
        )

    if state is not None:
        return run, cast(ReferenceFileMatchingState, state)

    # State doesn't exist - construct a default one from document processing state
    logger.info(
        f"No file matching state found for project {project_id}, constructing default"
    )

    doc_processing_state = await _get_document_processing_workflow_state(project_id, revision)
    if doc_processing_state is None:
        logger.info(
            f"No document processing state found for project {project_id}, "
            "cannot construct file matching state"
        )
        return run, None

    file_id = doc_processing_state.file.file_id
    supporting_file_ids = [
        f.file_id for f in (doc_processing_state.supporting_files or [])
    ]

    default_state = ReferenceFileMatchingState(
        type=WorkflowRunType.REFERENCE_FILE_MATCHING,
        config=ReferenceFileMatchingConfig(project_id=project_id),
        file_id=file_id,
        supporting_file_ids=supporting_file_ids,
        matches=[],
    )

    # Create workflow run if it doesn't exist
    if run is None:
        thread_id = str(uuid.uuid4())
        await create_workflow_run(
            project_id=project_id,
            status=WorkflowRunStatus.COMPLETED,
            type=WorkflowRunType.REFERENCE_FILE_MATCHING,
            thread_id=thread_id,
            revision=revision,
        )

        # Persist the default state to the checkpointer
        async with get_checkpointer() as checkpointer:
            graph = create_graph(WorkflowRunType.REFERENCE_FILE_MATCHING)
            app = graph.compile(checkpointer=checkpointer)

            await app.aupdate_state(
                {"configurable": {"thread_id": thread_id}},
                default_state.model_dump(),
                as_node="match_supporting_docs",
            )

        # Fetch the newly created workflow run
        run = await get_project_workflow_run_by_type(
            project_id, WorkflowRunType.REFERENCE_FILE_MATCHING, revision=revision
        )
        # Mirror the bootstrap state to state_json so the post-cutover reader
        # path matches what the checkpointer holds.
        if run is not None:
            await persist_workflow_run_state(str(run.id), default_state)
        logger.info(f"Created new file matching workflow run for project {project_id}")

    return run, default_state


async def _get_extraction_workflow_state(
    project_id: str,
    revision: int,
) -> Tuple[Optional[WorkflowRun], Optional[ReferenceExtractionState]]:
    """
    Get the ReferenceExtraction workflow run and state for a project.
    """
    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.REFERENCE_EXTRACTION, revision=revision
    )

    if run is None:
        logger.info(f"No ReferenceExtraction workflow found for project {project_id}")
        return None, None

    state = await get_workflow_run_state_by_thread_id(
        run.langgraph_thread_id, WorkflowRunType.REFERENCE_EXTRACTION
    )

    if state is None:
        logger.info(f"No extraction state found in workflow for project {project_id}")
        return run, None

    return run, cast(ReferenceExtractionState, state)


async def get_file_reference_matches(project_id: str, revision: int) -> List[ReferenceFileMatch]:
    """Return the current reference-file matches for a project (empty list if none)."""
    _, state = await _get_file_matching_workflow_state(project_id, revision)
    if state is None:
        return []
    return list(state.matches)


async def remove_file_from_references(project_id: str, file_id: str, revision: int) -> List[str]:
    """
    Remove file_id from any matches in the ReferenceFileMatching workflow state.

    This removes the file association by filtering out ReferenceFileMatch entries
    with the given file_id.

    Args:
        project_id: The project ID
        file_id: The file ID to remove from matches

    Returns:
        List of reference IDs that were unlinked (empty if no update was needed)
    """
    async with _project_lock(project_id):
        run, state = await _get_file_matching_workflow_state(project_id, revision)

        if run is None or state is None:
            return []

        # Find matches with this file_id
        removed_reference_ids: List[str] = []
        for match in state.matches:
            if match.file_id == file_id:
                removed_reference_ids.append(match.reference_id)

        if not removed_reference_ids:
            logger.info(f"No matches found with file_id {file_id}")
            return []

        # Filter out matches with this file_id
        updated_matches = [m for m in state.matches if m.file_id != file_id]

        # Update the state using LangGraph
        async with get_checkpointer() as checkpointer:
            graph = create_graph(WorkflowRunType.REFERENCE_FILE_MATCHING)
            app = graph.compile(checkpointer=checkpointer)

            await app.aupdate_state(
                {"configurable": {"thread_id": run.langgraph_thread_id}},
                {"matches": updated_matches},
                as_node="match_supporting_docs",
            )

        await persist_workflow_run_state(
            str(run.id), state.model_copy(update={"matches": updated_matches})
        )
        logger.info(
            f"Removed {len(removed_reference_ids)} matches with file_id {file_id}"
        )
        return removed_reference_ids


async def _get_downloader_workflow_state(
    project_id: str,
    revision: int,
) -> Tuple[Optional[WorkflowRun], Optional[ReferenceDownloaderState]]:
    """Get the ReferenceDownloader workflow run and state for a project."""
    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.REFERENCE_DOWNLOADER, revision=revision
    )
    if run is None:
        return None, None

    state = await get_workflow_run_state_by_thread_id(
        run.langgraph_thread_id, WorkflowRunType.REFERENCE_DOWNLOADER
    )
    return run, cast(Optional[ReferenceDownloaderState], state)


async def remove_fetch_result_for_file(
    project_id: str, file_id: str, revision: int
) -> int:
    """
    Remove any ReferenceDownloader fetch results whose downloaded file matches file_id.

    Called when a user deletes a file so the stale fetch result (e.g. "Source Found"
    pointing at a file that no longer exists) does not linger in workflow state.

    Returns the number of fetch_references entries that were removed.
    """
    async with _project_lock(project_id):
        run, state = await _get_downloader_workflow_state(project_id, revision)
        if run is None or state is None or not state.fetched_references:
            return 0

        filtered = [
            item
            for item in state.fetched_references
            if not (item.result and item.result.file_id == file_id)
        ]

        removed_count = len(state.fetched_references) - len(filtered)
        if removed_count == 0:
            return 0

        # Overwrite is required to bypass the merge_fetch_results reducer, which otherwise
        # upserts-only and would keep the entries we are trying to delete.
        async with get_checkpointer() as checkpointer:
            graph = create_graph(WorkflowRunType.REFERENCE_DOWNLOADER)
            app = graph.compile(checkpointer=checkpointer)

            await app.aupdate_state(
                {"configurable": {"thread_id": run.langgraph_thread_id}},
                {"fetched_references": Overwrite(filtered)},
                as_node="cleanup_failed_resources",
            )

        # Plain assignment of `filtered` is the Pydantic-level equivalent of
        # the checkpointer's Overwrite — both bypass the merge_fetch_results
        # reducer that would otherwise upsert-only.
        await persist_workflow_run_state(
            str(run.id), state.model_copy(update={"fetched_references": filtered})
        )
        logger.info(
            f"Removed {removed_count} fetch result(s) for file {file_id} in project {project_id}"
        )
        return removed_count


async def add_file_to_reference(
    project_id: str,
    file_id: str,
    reference_id: str,
    source: MatchSource,
    revision: int,
) -> bool:
    """
    Link a file to a specific reference in the ReferenceFileMatching workflow state.

    Args:
        project_id: The project ID
        file_id: The file ID to link to the reference
        reference_id: The ID of the reference to link the file to

    Returns:
        True if the reference was linked, False if no update was made
    """
    async with _project_lock(project_id):
        # Get file matching state
        run, state = await _get_file_matching_workflow_state(project_id, revision)
        if run is None or state is None:
            logger.warning(
                f"No file matching workflow found for project {project_id}, cannot add file"
            )
            return False

        _, extraction_state = await _get_extraction_workflow_state(project_id, revision)
        if extraction_state is None:
            logger.warning(f"No extraction state found for project {project_id}")
            return False

        valid_ids = {ref.id for ref in extraction_state.extracted_references if ref.id}
        if reference_id not in valid_ids:
            logger.warning(
                f"Invalid reference_id {reference_id} for project {project_id}"
            )
            return False

        # Remove any existing match for this reference_id, then add the new one
        updated_matches = [m for m in state.matches if m.reference_id != reference_id]
        updated_matches.append(
            ReferenceFileMatch(reference_id=reference_id, file_id=file_id, source=source)
        )

        # Update the state using LangGraph
        async with get_checkpointer() as checkpointer:
            graph = create_graph(WorkflowRunType.REFERENCE_FILE_MATCHING)
            app = graph.compile(checkpointer=checkpointer)

            await app.aupdate_state(
                {"configurable": {"thread_id": run.langgraph_thread_id}},
                {"matches": updated_matches},
                as_node="match_supporting_docs",
            )

        await persist_workflow_run_state(
            str(run.id), state.model_copy(update={"matches": updated_matches})
        )
        logger.info(
            f"Linked file {file_id} to reference {reference_id} in project {project_id}"
        )
        return True
