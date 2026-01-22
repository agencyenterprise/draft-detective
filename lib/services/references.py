import logging
from typing import List, Optional, Tuple

from lib.models.workflow_run import WorkflowRun
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.registry import create_graph

logger = logging.getLogger(__name__)


async def _get_reference_workflow_state(
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

    if state is None or not hasattr(state, "references") or not state.references:
        logger.info(f"No references found in workflow state for project {project_id}")
        return run, None

    return run, state


async def remove_file_from_references(project_id: str, file_id: str) -> List[str]:
    """
    Remove file_id from any references in the ReferenceExtraction workflow state.

    This clears the file association from BibliographyItems that reference the deleted file.

    Args:
        project_id: The project ID
        file_id: The file ID to remove from references

    Returns:
        List of reference texts that were updated (empty if no update was needed)
    """
    run, state = await _get_reference_workflow_state(project_id)

    if run is None or state is None:
        return []

    # Check if any references have this file_id and track their texts
    updated_reference_texts: List[str] = []
    for ref in state.references:
        if ref.file_id == file_id:
            updated_reference_texts.append(ref.text)

    if not updated_reference_texts:
        logger.info(f"No references found with file_id {file_id}")
        return []

    # Create updated references with file_id cleared
    updated_references = []
    for ref in state.references:
        if ref.file_id == file_id:
            updated_ref = ref.model_copy(
                update={
                    "file_id": None,
                    "has_associated_supporting_document": False,
                    "index_of_associated_supporting_document": -1,
                    "name_of_associated_supporting_document": "",
                }
            )
            updated_references.append(updated_ref)
        else:
            updated_references.append(ref)

    # Update the state using LangGraph
    async with get_checkpointer() as checkpointer:
        graph = create_graph(WorkflowRunType.REFERENCE_EXTRACTION)
        app = graph.compile(checkpointer=checkpointer)

        await app.aupdate_state(
            {"configurable": {"thread_id": run.langgraph_thread_id}},
            {"references": updated_references},
        )

    logger.info(
        f"Updated {len(updated_reference_texts)} references to remove file_id {file_id}"
    )
    return updated_reference_texts


async def add_file_to_reference(
    project_id: str,
    file_id: str,
    file_name: str,
    reference_index: int,
) -> bool:
    """
    Link a file to a specific reference in the ReferenceExtraction workflow state.

    Args:
        project_id: The project ID
        file_id: The file ID to link to the reference
        file_name: The name of the file (used for display)
        reference_index: The 0-based index of the reference to update

    Returns:
        True if the reference was updated, False if no update was needed
    """
    run, state = await _get_reference_workflow_state(project_id)

    if run is None or state is None:
        return False

    # Validate reference_index
    if reference_index < 0 or reference_index >= len(state.references):
        logger.warning(
            f"Invalid reference_index {reference_index} for project {project_id} "
            f"(has {len(state.references)} references)"
        )
        return False

    # Create updated references with the file linked to the specified reference
    updated_references = []
    for i, ref in enumerate(state.references):
        if i == reference_index:
            updated_ref = ref.model_copy(
                update={
                    "file_id": file_id,
                    "has_associated_supporting_document": True,
                    "index_of_associated_supporting_document": reference_index + 1,
                    "name_of_associated_supporting_document": file_name,
                }
            )
            updated_references.append(updated_ref)
        else:
            updated_references.append(ref)

    # Update the state using LangGraph
    async with get_checkpointer() as checkpointer:
        graph = create_graph(WorkflowRunType.REFERENCE_EXTRACTION)
        app = graph.compile(checkpointer=checkpointer)

        await app.aupdate_state(
            {"configurable": {"thread_id": run.langgraph_thread_id}},
            {"references": updated_references},
        )

    logger.info(
        f"Linked file {file_id} to reference {reference_index} in project {project_id}"
    )
    return True
