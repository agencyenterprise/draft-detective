import logging
from typing import List

from langgraph.runtime import Runtime

from lib.run_utils import run_tasks
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
    ReferenceFetchItem,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceFetchResult,
)

logger = logging.getLogger(__name__)


@register_node(
    "Fetch references",
    "Fetch references from the internet",
)
async def fetch_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    references = state.config.references or []

    reference_fetcher_agent = ReferenceFetcherAgent(runtime.context)
    fetch_references_tasks = [
        _fetch_reference(reference, reference_fetcher_agent) for reference in references
    ]
    results: tuple[list[ReferenceFetchItem | None], list[Exception | None]] = (
        await run_tasks(
            fetch_references_tasks,
            desc="Fetching references",
            max_concurrent=15,
        )
    )
    fetched_items, errors = results

    # Build results for ALL inputs (including errors)
    fetched_results: List[ReferenceFetchResult] = []
    for i, reference in enumerate(references):
        result = fetched_items[i]
        error = errors[i]

        if (
            result
            and result.final_conclusion != ReferenceFetchConclusion.SOURCE_FOUND
            and result.file_id
        ):
            # Sometimes the LLM will return a file ID for a non-found reference, so we need to clean it up
            result.file_id = None

        fetched_results.append(
            ReferenceFetchResult(
                input_reference=reference,
                result=result,
                error=str(error) if error else None,
            )
        )

    await _cleanup_failed_resources(runtime.context.project_id, fetched_results)

    return {"fetched_references": fetched_results}


async def _fetch_reference(
    reference: str, agent: ReferenceFetcherAgent
) -> ReferenceFetchItem:
    return await agent.ainvoke(ReferenceFetcherAgentInput(reference=reference))


async def _cleanup_failed_resources(
    project_id: str | None, items: List[ReferenceFetchResult]
) -> None:
    if not project_id:
        return

    valid_file_ids = {
        item.result.file_id
        for item in items
        if item.result
        and item.result.file_id
        and item.result.final_conclusion == ReferenceFetchConclusion.SOURCE_FOUND
    }

    candidate_files = await get_supporting_candidate_files(project_id)

    files_to_delete = [
        str(f.id) for f in candidate_files if str(f.id) not in valid_file_ids
    ]
    files_to_promote = [
        str(f.id) for f in candidate_files if str(f.id) in valid_file_ids
    ]

    if files_to_delete:
        deleted_count = delete_project_files(project_id, files_to_delete)
        logger.info(
            f"Deleted {deleted_count} failed reference files for project {project_id}"
        )
        if deleted_count != len(files_to_delete):
            logger.warning(
                f"Deleted {deleted_count} failed reference files for project {project_id}, but expected {len(files_to_delete)}"
            )

    if files_to_promote:
        update_files_role(files_to_promote, FileRole.SUPPORT)
        logger.info(
            f"Promoted {len(files_to_promote)} reference files to SUPPORT for project {project_id}"
        )
