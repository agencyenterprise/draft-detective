import asyncio
import logging
import os
from typing import Any, List, Tuple

from lib.workflows.base import WorkflowError

logger = logging.getLogger(__name__)


# This prevents overwhelming the tracing system and LLM APIs
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "15"))


async def run_tasks(
    tasks, desc="Processing tasks", max_concurrent=None
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

    # Use semaphore to limit concurrent executions
    semaphore = asyncio.Semaphore(max_concurrent)

    logger.info(
        f"{desc}: Running {len(tasks)} tasks with max concurrency of {max_concurrent}"
    )

    async def track_task(index, coro):
        async with semaphore:  # Acquire semaphore before running task
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

    task_results = []
    task_errors = []

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
    task_name: str, exceptions: List[Exception | None]
) -> List[WorkflowError]:
    errors: List[WorkflowError] = []
    for chunk_index, exception in enumerate(exceptions):
        if exception is not None:
            errors.append(
                WorkflowError(
                    task_name=task_name,
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )
    return errors
