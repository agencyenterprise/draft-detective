import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.files.service import (
    get_main_file_id,
    get_processed_supporting_file_ids,
)
from lib.services.workflow_runs.service import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    get_project_workflow_run_with_state,
    persist_workflow_run_state,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_downloader.state import ReferenceDownloaderState
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)

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

    This serializes the functions in this module that update a project's
    reference state, while operations on different projects can proceed in
    parallel. The lock lives in this process and covers only these functions:
    a running workflow persisting its own state does not take it.
    """
    lock = _get_project_lock(project_id)
    async with lock:
        yield


async def _get_file_matching_workflow_state(
    project_id: str,
    revision: int,
) -> tuple[WorkflowRun | None, ReferenceFileMatchingState | None]:
    """
    Get the ReferenceFileMatching workflow run and state for a project revision.

    When the run holds no usable state, builds a default ReferenceFileMatchingState
    with empty matches from the revision's main and processed supporting files.
    With no run, it first creates a COMPLETED run and persists that default on
    it; a run with no state_json gets the default persisted. A run whose
    state_json fails to hydrate keeps its payload, and the default is returned
    without being saved.

    Args:
        project_id: The project ID
        revision: The project revision

    Returns:
        Tuple of (workflow_run, state), or (run, None) when there is no state
        and the revision has no main file to build a default from (the run is
        then None if none existed)
    """
    run, state = await get_project_workflow_run_with_state(
        project_id, ReferenceFileMatchingState, revision
    )
    if state is not None:
        return run, state

    # State doesn't exist - construct a default one from the file table
    logger.info(
        f"No file matching state found for project {project_id}, constructing default"
    )

    try:
        file_id = await get_main_file_id(project_id, revision)
    except ValueError:
        logger.info(
            f"No main file found for project {project_id} revision {revision}, "
            "cannot construct file matching state"
        )
        return run, None
    supporting_file_ids = await get_processed_supporting_file_ids(project_id, revision)

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

        # Fetch the newly created workflow run and seed its (empty) state so
        # reads-without-mutation leave the row consistent with what callers get.
        run = await get_project_workflow_run_by_type(
            project_id, WorkflowRunType.REFERENCE_FILE_MATCHING, revision=revision
        )
        if run is not None:
            await persist_workflow_run_state(str(run.id), default_state)
        logger.info(f"Created new file matching workflow run for project {project_id}")
    elif run.state_json is None:
        # Existing run whose row has no persisted state yet — seed the default.
        # Guard on `state_json IS NULL` (the loader above loads it with the run),
        # NOT on "the loader returned no state": the latter is also true
        # when state_json is present but fails to hydrate (schema drift), and we
        # must not clobber that existing payload with an empty default.
        await persist_workflow_run_state(str(run.id), default_state)

    return run, default_state


async def get_file_reference_matches(
    project_id: str, revision: int
) -> list[ReferenceFileMatch]:
    """Return the current reference-file matches for a project (empty list if none)."""
    _, state = await _get_file_matching_workflow_state(project_id, revision)
    if state is None:
        return []
    return list(state.matches)


async def remove_file_from_references(
    project_id: str, file_id: str, revision: int
) -> list[str]:
    """
    Remove file_id from any matches in the ReferenceFileMatching workflow state.

    This removes the file association by filtering out ReferenceFileMatch entries
    with the given file_id.

    Args:
        project_id: The project ID
        file_id: The file ID to remove from matches
        revision: The project revision

    Returns:
        List of reference IDs that were unlinked (empty if no update was needed)
    """
    async with _project_lock(project_id):
        run, state = await _get_file_matching_workflow_state(project_id, revision)

        if run is None or state is None:
            return []

        # Find matches with this file_id
        removed_reference_ids: list[str] = []
        for match in state.matches:
            if match.file_id == file_id:
                removed_reference_ids.append(match.reference_id)

        if not removed_reference_ids:
            logger.info(f"No matches found with file_id {file_id}")
            return []

        # Filter out matches with this file_id
        updated_matches = [m for m in state.matches if m.file_id != file_id]

        await persist_workflow_run_state(
            str(run.id), state.model_copy(update={"matches": updated_matches})
        )
        logger.info(
            f"Removed {len(removed_reference_ids)} matches with file_id {file_id}"
        )
        return removed_reference_ids


async def remove_fetch_result_for_file(
    project_id: str, file_id: str, revision: int
) -> int:
    """
    Remove any ReferenceDownloader fetch results whose downloaded file matches file_id.

    Called when a user deletes a file so the stale fetch result (e.g. "Source Found"
    pointing at a file that no longer exists) does not linger in workflow state.

    Returns the number of fetched_references entries that were removed.
    """
    async with _project_lock(project_id):
        run, state = await get_project_workflow_run_with_state(
            project_id, ReferenceDownloaderState, revision
        )
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

        # Plain assignment of `filtered` bypasses the merge_fetch_results reducer
        # (which upserts-only) so the deleted entries are actually dropped.
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
        source: How the file came to be linked (manual upload, auto-fetched, ...)
        revision: The project revision

    Returns:
        True if the reference was linked; False, with nothing changed, when the
        revision has no main file or no reference extraction state, or the
        extraction has no reference with this ID. Any earlier match for the
        reference is replaced.
    """
    async with _project_lock(project_id):
        # Get file matching state
        run, state = await _get_file_matching_workflow_state(project_id, revision)
        if run is None or state is None:
            logger.warning(
                f"No file matching workflow found for project {project_id}, cannot add file"
            )
            return False

        _, extraction_state = await get_project_workflow_run_with_state(
            project_id, ReferenceExtractionState, revision
        )
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
            ReferenceFileMatch(
                reference_id=reference_id, file_id=file_id, source=source
            )
        )

        await persist_workflow_run_state(
            str(run.id), state.model_copy(update={"matches": updated_matches})
        )
        logger.info(
            f"Linked file {file_id} to reference {reference_id} in project {project_id}"
        )
        return True
