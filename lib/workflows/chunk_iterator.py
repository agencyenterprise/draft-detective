from typing import Callable, List, Tuple

from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.models import BaseWorkflowState


def get_target_chunks(state: BaseWorkflowState) -> List[AnalyzedChunk]:
    config = getattr(state, "config", None)
    target_chunk_indices = getattr(config, "target_chunk_indices", None)

    if not target_chunk_indices:
        return getattr(state, "chunks", [])

    return [state.chunks[index] for index in target_chunk_indices]


async def iterate_chunks(
    state: BaseWorkflowState,
    func: Callable[[BaseWorkflowState, AnalyzedChunk, ...], AnalyzedChunk],
    desc: str,
    **kwargs: ...,
) -> BaseWorkflowState:
    """
    Iterate over chunks and process them with automatic progress tracking.

    Progress tracking is handled automatically via contextvars set by the
    @register_node decorator. No explicit runtime parameter needed.

    Args:
        state: Workflow state
        func: Function to process each chunk
        desc: Description for logging and progress
        **kwargs: Additional arguments to pass to func

    Returns:
        Updated state with chunks and errors
    """
    target_chunks = get_target_chunks(state)

    # run_tasks() automatically tracks progress via contextvars
    tasks = [func(state, chunk, **kwargs) for chunk in target_chunks]
    results: Tuple[List[AnalyzedChunk], List[Exception]] = await run_tasks(
        tasks, desc=desc
    )
    updated_chunks, exceptions = results

    chunk_indices = [c.chunk_index for c in target_chunks]
    errors = convert_exceptions_to_workflow_errors(
        func.__name__, exceptions, chunk_indices
    )

    return {"chunks": updated_chunks, "errors": errors}
