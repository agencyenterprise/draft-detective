from typing import Callable, List, Tuple

from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.models import BaseWorkflowState, WorkflowError


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
    target_chunks = get_target_chunks(state)

    tasks = [func(state, chunk, **kwargs) for chunk in target_chunks]
    results: Tuple[List[AnalyzedChunk], List[Exception]] = await run_tasks(
        tasks, desc=desc
    )
    updated_chunks, exceptions = results

    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = target_chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name=func.__name__,
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    return {"chunks": updated_chunks, "errors": errors}
