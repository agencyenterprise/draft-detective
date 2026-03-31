import logging
from typing import List

from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.models.file import FileRole
from lib.services.files import (
    delete_project_files,
    get_supporting_candidate_files,
    update_files_role,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchConclusion,
    ReferenceFetcherAgent,
    ReferenceFetcherAgentInput,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)

logger = logging.getLogger(__name__)


@register_node("Initialize references")
async def initialize_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Initialize all references with PENDING status immediately.

    This allows the frontend to display all references right away
    before any fetching has started.
    """
    references = state.config.references or []

    pending_results = [
        ReferenceFetchResult(
            reference_id=ref.reference_id,
            input_reference=ref.text,
            status=ReferenceFetchStatus.PENDING,
        )
        for ref in references
    ]

    # Overwrite is needed in case references changed since last run
    return {"fetched_references": Overwrite(pending_results)}


@register_node("Distribute references")
async def distribute_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each reference.

    This node dispatches parallel fetch operations for each reference.
    """
    references = state.config.references or []
    return [
        Send(
            "fetch_single_reference",
            {"reference": ref.text, "reference_id": ref.reference_id},
        )
        for ref in references
    ]


@register_node("Fetch reference")
async def fetch_single_reference(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single reference and return status update.

    Each call to this node handles one reference and returns an update
    that the reducer will merge into the state by reference_id.
    """
    reference = state["reference"]
    reference_id = state["reference_id"]

    agent = ReferenceFetcherAgent(runtime.context)

    project_id = runtime.context.project_id
    result = None
    error = None
    status = ReferenceFetchStatus.COMPLETED

    try:
        result, _ = await agent.ainvoke(ReferenceFetcherAgentInput(reference=reference))

        if (
            result
            and result.final_conclusion != ReferenceFetchConclusion.SOURCE_FOUND
            and result.file_id
        ):
            # Sometimes the LLM will return a file ID for a non-found reference, so we need to clean it up
            result.file_id = None

        if status == ReferenceFetchStatus.COMPLETED and result and result.file_id:
            # Promote file immediately (from SUPPORTING_CANDIDATE to SUPPORT)
            await update_files_role([result.file_id], FileRole.SUPPORT)
            # Update the reference file matching in the ReferenceExtraction workflow state
            await _update_reference_file_matching(
                project_id, result.file_id, reference_id
            )

    except Exception as e:
        logger.error(f"Error fetching reference '{reference}': {e}", exc_info=True)
        status = ReferenceFetchStatus.ERROR
        error = str(e)

    return {
        "fetched_references": [
            ReferenceFetchResult(
                reference_id=reference_id,
                input_reference=reference,
                status=status,
                result=result,
                error=error,
            )
        ]
    }


@register_node("Cleanup")
async def cleanup_failed_resources(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Clean up files for failed references and promote successful ones."""
    project_id = runtime.context.project_id
    fetched_references = state.fetched_references

    if not fetched_references:
        return {}

    valid_file_ids = {
        item.result.file_id
        for item in fetched_references
        if item.result
        and item.result.file_id
        and item.result.final_conclusion == ReferenceFetchConclusion.SOURCE_FOUND
    }

    candidate_files = await get_supporting_candidate_files(project_id)

    files_to_delete: List[str] = []
    files_to_promote: List[str] = []

    for f in candidate_files:
        file_id = str(f.id)
        if file_id in valid_file_ids:
            files_to_promote.append(file_id)
        else:
            files_to_delete.append(file_id)

    if files_to_delete:
        deleted_count = await delete_project_files(project_id, files_to_delete)
        logger.info(
            f"Deleted {deleted_count} failed reference files for project {project_id}"
        )
        if deleted_count != len(files_to_delete):
            logger.warning(
                f"Deleted {deleted_count} files, but expected {len(files_to_delete)}"
            )

    if files_to_promote:
        await update_files_role(files_to_promote, FileRole.SUPPORT)
        logger.info(
            f"Promoted {len(files_to_promote)} reference files to SUPPORT for project {project_id}"
        )

    return {}


async def _update_reference_file_matching(
    project_id: str, file_id: str, reference_id: str
):
    """Update the reference file matching in the ReferenceExtraction workflow state."""

    from lib.services.references import add_file_to_reference
    from lib.workflows.reference_file_matching.state import MatchSource

    await add_file_to_reference(
        project_id=project_id,
        file_id=file_id,
        reference_id=reference_id,
        source=MatchSource.AUTO_FETCHED,
    )
