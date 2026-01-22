import logging
import uuid
from typing import List, Optional, Tuple

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_workflow_run_state_by_thread_id,
    create_workflow_run,
)
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatch,
    ReferenceFileMatchingState,
)
from lib.workflows.registry import create_graph

logger = logging.getLogger(__name__)


async def _get_document_processing_workflow_state(project_id: str):
    """Get the DocumentProcessing workflow state for a project."""
    from lib.workflows.document_processing.state import DocumentProcessingState

    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.DOCUMENT_PROCESSING
    )
    if run is None:
        return None

    state = await get_workflow_run_state_by_thread_id(
        run.langgraph_thread_id, WorkflowRunType.DOCUMENT_PROCESSING
    )
    return state


async def _get_file_matching_workflow_state(
    project_id: str,
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
        project_id, WorkflowRunType.REFERENCE_FILE_MATCHING
    )

    state = None
    if run is not None:
        state = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, WorkflowRunType.REFERENCE_FILE_MATCHING
        )

    if state is not None:
        return run, state

    # State doesn't exist - construct a default one from document processing state
    logger.info(
        f"No file matching state found for project {project_id}, constructing default"
    )

    doc_processing_state = await _get_document_processing_workflow_state(project_id)
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
        config=ReferenceFileMatchingConfig(),
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
            project_id, WorkflowRunType.REFERENCE_FILE_MATCHING
        )
        logger.info(f"Created new file matching workflow run for project {project_id}")

    return run, default_state


async def _get_extraction_workflow_state(
    project_id: str,
) -> Tuple[Optional[WorkflowRun], Optional[ReferenceExtractionState]]:
    """
    Get the ReferenceExtraction workflow run and state for a project.

    Args:
        project_id: The project ID

    Returns:
        Tuple of (workflow_run, state) or (None, None) if not found
    """
    run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.REFERENCE_EXTRACTION
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

    return run, state


async def remove_file_from_references(project_id: str, file_id: str) -> List[str]:
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
    run, state = await _get_file_matching_workflow_state(project_id)

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
        )

    logger.info(f"Removed {len(removed_reference_ids)} matches with file_id {file_id}")
    return removed_reference_ids


async def add_file_to_reference(
    project_id: str,
    file_id: str,
    file_name: str,
    reference_index: int,
) -> bool:
    """
    Link a file to a specific reference in the ReferenceFileMatching workflow state.

    Args:
        project_id: The project ID
        file_id: The file ID to link to the reference
        file_name: The name of the file (unused, kept for API compatibility)
        reference_index: The 0-based index of the reference to update

    Returns:
        True if the reference was linked, False if no update was made
    """
    # Get extraction state to find reference_id at the given index
    _, extraction_state = await _get_extraction_workflow_state(project_id)
    if extraction_state is None:
        logger.warning(
            f"No extraction state found for project {project_id}, cannot add file"
        )
        return False

    # Validate reference_index
    extracted_refs = extraction_state.extracted_references
    if reference_index < 0 or reference_index >= len(extracted_refs):
        logger.warning(
            f"Invalid reference_index {reference_index} for project {project_id} "
            f"(has {len(extracted_refs)} references)"
        )
        return False

    reference_id = extracted_refs[reference_index].id

    # Get file matching state
    run, state = await _get_file_matching_workflow_state(project_id)
    if run is None or state is None:
        logger.warning(
            f"No file matching workflow found for project {project_id}, cannot add file"
        )
        return False

    # Remove any existing match for this reference_id, then add the new one
    updated_matches = [m for m in state.matches if m.reference_id != reference_id]
    updated_matches.append(
        ReferenceFileMatch(reference_id=reference_id, file_id=file_id)
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

    logger.info(
        f"Linked file {file_id} to reference {reference_id} in project {project_id}"
    )
    return True
