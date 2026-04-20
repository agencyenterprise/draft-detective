"""Workflow decorators for consistent behavior across nodes."""

import asyncio
import logging
import time
import uuid
from contextvars import Token
from functools import wraps
from typing import Any, Callable

from langgraph.runtime import Runtime

from lib.models.workflow_progress import ProgressLevel
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.workflow_progress import (
    get_or_create_progress,
    increment_and_complete_if_done,
)
from lib.workflows.context import ContextSchema, current_progress_id
from lib.workflows.models import (
    BaseWorkflowState,
    WorkflowCancelledError,
    WorkflowError,
)

CANCELLATION_CHECK_INTERVAL = 5.0


async def _poll_for_cancellation(
    workflow_run_id: str, node_task: asyncio.Task, interval: float
) -> None:
    """Poll the DB for cancellation status and cancel the node task if detected."""
    from lib.services.workflow_runs import get_workflow_run_status

    while not node_task.done():
        await asyncio.sleep(interval)
        if node_task.done():
            break
        status = await get_workflow_run_status(workflow_run_id)
        if status == WorkflowRunStatus.CANCELLED:
            node_task.cancel()
            break


async def _setup_progress(
    workflow_run_id: str, name: str, logger: logging.Logger
) -> tuple[str, Token]:
    """Create or get the progress entry and store its ID in the current context."""
    progress_uuid = await get_or_create_progress(
        workflow_run_id=uuid.UUID(workflow_run_id),
        name=name,
        level=ProgressLevel.NODE,
    )
    token = current_progress_id.set(progress_uuid)
    progress_id = str(progress_uuid)
    logger.info(f"Progress tracking: {name} started (progress_id: {progress_id})")
    return progress_id, token


async def _check_cancellation(workflow_run_id: str, func_name: str) -> None:
    """Raise WorkflowCancelledError if the workflow is already cancelled."""
    from lib.services.workflow_runs import get_workflow_run_status

    status = await get_workflow_run_status(workflow_run_id)
    if status == WorkflowRunStatus.CANCELLED:
        raise WorkflowCancelledError(
            f"Workflow {workflow_run_id} was cancelled before node {func_name}"
        )


async def _run_node_with_cancellation(
    func: Callable,
    state: BaseWorkflowState,
    runtime: Runtime[ContextSchema],
    workflow_run_id: str,
) -> dict[str, Any]:
    """Run the node function alongside a cancellation poller."""
    from lib.services.workflow_runs import get_workflow_run_status

    node_task = asyncio.ensure_future(func(state, runtime))
    poll_task = asyncio.ensure_future(
        _poll_for_cancellation(workflow_run_id, node_task, CANCELLATION_CHECK_INTERVAL)
    )
    try:
        return await node_task
    except asyncio.CancelledError:
        # Confirm the cancellation came from our poller and not an external event loop shutdown
        status = await get_workflow_run_status(workflow_run_id)
        if status == WorkflowRunStatus.CANCELLED:
            raise WorkflowCancelledError(
                f"Workflow {workflow_run_id} was cancelled during node {func.__name__}"
            )
        raise
    finally:
        poll_task.cancel()
        await asyncio.gather(poll_task, return_exceptions=True)


async def _complete_progress(
    progress_id: str, name: str, logger: logging.Logger
) -> None:
    """Increment progress and log whether the full batch completed."""
    completed = await increment_and_complete_if_done(uuid.UUID(progress_id))
    label = "batch completed" if completed else "step completed"
    logger.info(f"Progress tracking: {name} {label} (progress_id: {progress_id})")


def register_node(name: str):
    """
    Decorator to control the execution of a workflow node.

    - Logs the start and end of the node, during execution
    - Handles errors and updates the state with a WorkflowError object, during execution

    Args:
        name: A human-readable name of the node.
    """

    def decorator(
        func: Callable[[BaseWorkflowState, Runtime[ContextSchema]], dict[str, Any]],
    ):
        func_logger = logging.getLogger(func.__module__)

        @wraps(func)
        async def wrapper(
            state: BaseWorkflowState, runtime: Runtime[ContextSchema]
        ) -> dict[str, Any]:

            workflow_run_id = runtime.context.workflow_run_id
            if not workflow_run_id:
                raise ValueError("Workflow run ID is not set in the context")

            project_id = runtime.context.project_id
            func_logger.info(f"{func.__name__} ({project_id}): starting")
            start_time = time.time()

            progress_id, progress_token = await _setup_progress(
                workflow_run_id, name, func_logger
            )

            try:
                await _check_cancellation(workflow_run_id, func.__name__)

                result = await _run_node_with_cancellation(
                    func, state, runtime, workflow_run_id
                )

                func_logger.info(
                    f"{func.__name__} ({project_id}): done in {time.time() - start_time:.2f} seconds"
                )
                return result

            except WorkflowCancelledError:
                func_logger.info(
                    f"{func.__name__} ({project_id}): node skipped — workflow was cancelled"
                )
                raise

            except Exception as e:
                func_logger.error(
                    f"{func.__name__} ({project_id}): workflow node execution failed with error: {e}",
                    exc_info=True,
                )
                return {
                    "errors": [
                        WorkflowError(
                            task_name=func.__name__,
                            error=str(e),
                            workflow_run_id=workflow_run_id,
                        )
                    ]
                }

            finally:
                await _complete_progress(progress_id, name, func_logger)

                current_progress_id.reset(progress_token)

        return wrapper

    return decorator
