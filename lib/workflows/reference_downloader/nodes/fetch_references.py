import logging
from typing import List

from langgraph.runtime import Runtime
from langgraph.types import Send

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


@register_node(
    "Initialize references",
    "Initialize all references with pending status",
)
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
            index=i,
            input_reference=ref,
            status=ReferenceFetchStatus.PENDING,
        )
        for i, ref in enumerate(references)
    ]

    return {"fetched_references": pending_results}


async def distribute_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each reference.

    This node dispatches parallel fetch operations for each reference.
    """
    references = state.config.references or []
    return [
        Send("fetch_single_reference", {"reference": ref, "index": i})
        for i, ref in enumerate(references)
    ]


async def fetch_single_reference(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single reference and return status update.

    Each call to this node handles one reference and returns an update
    that the reducer will merge into the state by index.
    """
    reference = state["reference"]
    index = state["index"]

    agent = ReferenceFetcherAgent(runtime.context)

    result = None
    error = None
    status = ReferenceFetchStatus.COMPLETED

    try:
        result = await agent.ainvoke(ReferenceFetcherAgentInput(reference=reference))

        if (
            result
            and result.final_conclusion != ReferenceFetchConclusion.SOURCE_FOUND
            and result.file_id
        ):
            # Sometimes the LLM will return a file ID for a non-found reference, so we need to clean it up
            result.file_id = None

    except Exception as e:
        logger.error(f"Error fetching reference '{reference}': {e}", exc_info=True)
        status = ReferenceFetchStatus.ERROR
        error = str(e)

    return {
        "fetched_references": [
            ReferenceFetchResult(
                index=index,
                input_reference=reference,
                status=status,
                result=result,
                error=error,
            )
        ]
    }


@register_node(
    "Cleanup failed resources",
    "Clean up files for failed references",
)
async def cleanup_failed_resources(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Clean up files for failed references and promote successful ones."""
    project_id = runtime.context.project_id
    fetched_references = state.fetched_references

    if not project_id or not fetched_references:
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
        deleted_count = delete_project_files(project_id, files_to_delete)
        logger.info(
            f"Deleted {deleted_count} failed reference files for project {project_id}"
        )
        if deleted_count != len(files_to_delete):
            logger.warning(
                f"Deleted {deleted_count} files, but expected {len(files_to_delete)}"
            )

    if files_to_promote:
        update_files_role(files_to_promote, FileRole.SUPPORT)
        logger.info(
            f"Promoted {len(files_to_promote)} reference files to SUPPORT for project {project_id}"
        )

    return {}
