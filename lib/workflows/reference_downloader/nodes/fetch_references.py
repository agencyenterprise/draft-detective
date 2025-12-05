import asyncio

from langgraph.runtime import Runtime

from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetcherAgent,
    ReferenceFetcherAgentInput,
    ReferenceFetchItem,
)
from lib.workflows.reference_downloader.state import ReferenceDownloaderState


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
    results: tuple[list[ReferenceFetchItem], list[Exception]] = await run_tasks(
        fetch_references_tasks, desc="Fetching references"
    )
    fetched_references, errors = results

    return {"fetched_references": fetched_references}


async def _fetch_reference(
    reference: str, agent: ReferenceFetcherAgent
) -> ReferenceFetchItem:
    return await agent.ainvoke(ReferenceFetcherAgentInput(reference=reference))
