import logging
from typing import List

from langgraph.runtime import Runtime

from lib.run_utils import run_tasks
from lib.services.files import delete_project_files
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetcherAgent,
    ReferenceFetcherAgentInput,
    ReferenceFetchItem,
)
from lib.workflows.reference_downloader.state import ReferenceDownloaderState

logger = logging.getLogger(__name__)


@register_node(
    "Fetch references",
    "Fetch references from the internet",
)
async def fetch_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
) -> ReferenceDownloaderState:
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
    fetched_references, errors = results
    valid_fetched_references: List[ReferenceFetchItem] = [
        result for result in fetched_references if result is not None
    ]

    _cleanup_failed_resources(runtime.context.project_id, valid_fetched_references)

    return {"fetched_references": valid_fetched_references}


async def _fetch_reference(
    reference: str, agent: ReferenceFetcherAgent
) -> ReferenceFetchItem:
    return await agent.ainvoke(ReferenceFetcherAgentInput(reference=reference))


def _cleanup_failed_resources(project_id: str, items: List[ReferenceFetchItem]) -> None:
    failed_file_ids: List[str] = []

    for item in items:
        if item is not None:
            failed_file_ids.extend(item.failed_file_ids)

    if not failed_file_ids:
        return

    delete_project_files(project_id, failed_file_ids)
    logger.info(f"Deleted {len(failed_file_ids)} failed files for project {project_id}")
