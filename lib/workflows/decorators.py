"""Workflow decorators for consistent behavior across nodes."""

import logging
import time
import uuid
from contextvars import Token
from functools import wraps
from typing import Callable, Optional, TypeVar

from langgraph.runtime import Runtime

from lib.models.workflow_progress import ProgressLevel
from lib.services.workflow_progress import (
    get_or_create_progress,
    increment_and_complete_if_done,
)
from lib.workflows.context import (
    ContextSchema,
    current_progress_id,
)
from lib.workflows.models import BaseWorkflowState, WorkflowError

# Type variable for decorator return types
T = TypeVar("T")


def register_node(name: str, description: str):
    """
    Decorator to control the execution of a workflow node.

    - Skips the node if it is not in the agents_to_run configuration, during execution
    - Logs the start and end of the node, during execution
    - Handles errors and updates the state with a WorkflowError object, during execution

    Args:
        name: A human-readable name of the node.
        description: A human-readable description of the node.
    """

    def decorator(
        func: Callable[[BaseWorkflowState, ...], BaseWorkflowState],
    ) -> Callable[[BaseWorkflowState, ...], BaseWorkflowState]:

        func_logger = logging.getLogger(func.__module__)

        @wraps(func)
        async def wrapper(
            state: BaseWorkflowState, runtime: Runtime[ContextSchema]
        ) -> BaseWorkflowState:

            config = getattr(state, "config", None)
            project_id = config.project_id if config else None
            agents_to_run = getattr(config, "agents_to_run", None)

            if agents_to_run and func.__name__ not in agents_to_run:
                func_logger.info(
                    f"{func.__name__} ({project_id}): skipping (not in agents_to_run)"
                )
                return {}

            func_logger.info(f"{func.__name__} ({project_id}): starting")
            start_time = time.time()

            # Progress tracking: create and start progress entry
            progress_id: Optional[uuid.UUID] = None
            progress_token: Optional[Token] = None
            workflow_run_id_str: Optional[str] = None

            try:
                if runtime and hasattr(runtime, "context"):
                    workflow_run_id_str = getattr(
                        runtime.context, "workflow_run_id", None
                    )

                    if workflow_run_id_str:
                        try:
                            # Convert string to UUID
                            workflow_run_id = uuid.UUID(workflow_run_id_str)

                            # Use get_or_create to enable automatic batching
                            # of parallel nodes with the same name
                            progress_id = await get_or_create_progress(
                                workflow_run_id=workflow_run_id,
                                name=name,
                                level=ProgressLevel.NODE,
                            )

                            # Store token for cleanup to prevent leakage
                            progress_token = current_progress_id.set(progress_id)

                            func_logger.info(
                                f"Progress tracking: {name} started (progress_id: {progress_id})"
                            )
                        except Exception as e:
                            func_logger.error(
                                f"Progress tracking failed for {name}: {e}",
                                exc_info=True,
                            )

                result = await func(state, runtime)

                # Increment progress and complete if all parallel nodes are done
                if progress_id:
                    try:
                        completed = await increment_and_complete_if_done(progress_id)
                        if completed:
                            func_logger.info(
                                f"Progress tracking: {name} batch completed (progress_id: {progress_id})"
                            )
                        else:
                            func_logger.info(
                                f"Progress tracking: {name} step completed (progress_id: {progress_id})"
                            )
                    except Exception as e:
                        func_logger.error(
                            f"Failed to update progress entry: {e}", exc_info=True
                        )

                func_logger.info(
                    f"{func.__name__} ({project_id}): done in {time.time() - start_time:.2f} seconds"
                )

                return result

            except Exception as e:
                # Still increment progress on error so batch can complete
                if progress_id:
                    try:
                        await increment_and_complete_if_done(progress_id)
                    except Exception as progress_error:
                        func_logger.error(
                            f"Failed to update progress on error: {progress_error}",
                            exc_info=True,
                        )

                func_logger.error(
                    f"{func.__name__} ({project_id}): workflow node execution failed with error: {str(e)}",
                    exc_info=True,
                )
                return {
                    "errors": [
                        WorkflowError(
                            task_name=func.__name__,
                            error=str(e),
                            workflow_run_id=workflow_run_id_str,
                        )
                    ]
                }

            finally:
                # CRITICAL: Reset contextvars to prevent leakage to subsequent nodes
                if progress_token is not None:
                    current_progress_id.reset(progress_token)

        return wrapper

    return decorator
