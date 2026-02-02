import asyncio
import logging
import os
from typing import Any, List, Optional, Tuple
from uuid import UUID

from lib.workflows.context import current_progress_id
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


# This prevents overwhelming the tracing system and LLM APIs
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "15"))


def _get_progress_id() -> Optional[UUID]:
    """Get progress ID from context variable if available."""
    try:
        return current_progress_id.get()
    except Exception:
        return None


async def _update_progress_safely(progress_id: UUID, **kwargs) -> None:
    """Update progress with error handling."""
    try:
        # Import here to avoid circular dependency at module load time
        from lib.services.workflow_progress import update_progress

        await update_progress(progress_id, **kwargs)
    except Exception as e:
        logger.warning(f"Failed to update progress: {e}")


async def run_tasks(
    tasks,
    desc="Processing tasks",
    max_concurrent=None,
) -> Tuple[List[Any | None], List[Exception | None]]:
    """
    Run tasks with concurrency limit to avoid overwhelming systems.

    Args:
        tasks: List of coroutines to run
        desc: Description for progress bar
        max_concurrent: Maximum number of concurrent tasks (default: MAX_CONCURRENT_TASKS env var or 15)

    Returns:
        Tuple of (results, errors) lists
    """
    if max_concurrent is None:
        max_concurrent = MAX_CONCURRENT_TASKS

    semaphore = asyncio.Semaphore(max_concurrent)

    logger.info(
        f"{desc}: Running {len(tasks)} tasks with max concurrency of {max_concurrent}"
    )

    progress_id = _get_progress_id()

    # Update node's total_steps to reflect actual task count
    if progress_id and len(tasks) > 1:
        await _update_progress_safely(progress_id, total_steps=len(tasks))

    async def track_task(index, coro):
        async with semaphore:
            try:
                return index, await coro, None
            except Exception as e:
                logger.error(
                    f"Error processing task {index}: {e}",
                    exc_info=True,
                )
                return index, None, e

    wrapped_tasks = [track_task(i, coro) for i, coro in enumerate(tasks)]

    task_results_dict = {}
    task_errors_dict = {}
    completed_count = 0
    for finished_task in asyncio.as_completed(wrapped_tasks):
        original_index, result, error = await finished_task
        task_results_dict[original_index] = result
        task_errors_dict[original_index] = error
        completed_count += 1
        logger.info(
            f"{desc}: Completed {completed_count} / {len(tasks)} (Task #{original_index} completed)"
        )

        if progress_id:
            await _update_progress_safely(progress_id, current_step=completed_count)

    task_results: List[Any | None] = []
    task_errors: List[Exception | None] = []

    for chunk_index in range(len(tasks)):
        if chunk_index not in task_results_dict:
            task_results.append(None)
            task_errors.append(None)
        else:
            task_results.append(task_results_dict[chunk_index])
            task_errors.append(task_errors_dict[chunk_index])
    return task_results, task_errors


def maybe_async(func):
    """Decorator that makes any function callable with await, regardless of sync/async."""

    async def wrapper(*args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper


async def call_maybe_async(func, *args, **kwargs):
    """Call a function, handling both sync and async cases automatically."""
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)


def convert_exceptions_to_workflow_errors(
    task_name: str,
    exceptions: List[Exception | None],
    chunk_indices: Optional[List[int]] = None,
    workflow_run_id: Optional[str] = None,
) -> List[WorkflowError]:
    """
    Convert a list of exceptions to WorkflowError objects.

    Args:
        task_name: The name of the task that caused the errors.
        exceptions: List of exceptions (None for successful tasks).
        chunk_indices: Optional list of chunk indices corresponding to each exception.
                      If None, no chunk_index is set on errors.
                      If provided, must be same length as exceptions.
        workflow_run_id: Optional workflow run ID to tag errors with.

    Raises:
        ValueError: If chunk_indices is provided but has different length than exceptions.
    """
    if chunk_indices is not None and len(chunk_indices) != len(exceptions):
        raise ValueError(
            f"chunk_indices length ({len(chunk_indices)}) must match "
            f"exceptions length ({len(exceptions)})"
        )

    errors: List[WorkflowError] = []
    for i, exception in enumerate(exceptions):
        if exception is not None:
            errors.append(
                WorkflowError(
                    task_name=task_name,
                    error=str(exception),
                    chunk_index=chunk_indices[i] if chunk_indices else None,
                    workflow_run_id=workflow_run_id,
                )
            )
    return errors
