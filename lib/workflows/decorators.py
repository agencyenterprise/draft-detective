"""Workflow decorators for consistent behavior across nodes."""

import logging
import time
from functools import wraps
from typing import Callable, TypeVar

from lib.agents.registry import agent_registry
from lib.workflows.claim_substantiation.state import (
    AnalyzedChunk,
    ClaimSubstantiatorState,
)
from lib.workflows.base import BaseWorkflowState, WorkflowError

# Type variable for decorator return types
T = TypeVar("T")


def handle_chunk_errors(operation_name: str):
    """
    Decorator for consistent chunk processing error handling.

    Catches exceptions during chunk processing, logs them with context,
    and re-raises with a truncated message to avoid massive error messages.

    Args:
        operation_name: Human-readable name of the operation for error messages

    Returns:
        Decorator that wraps async chunk processing functions

    Example:
        @handle_chunk_errors("Claim extraction")
        async def _extract_chunk_claims(
            state: ClaimSubstantiatorState, chunk: AnalyzedChunk
        ) -> AnalyzedChunk:
            ...
    """

    def decorator(
        func: Callable[[ClaimSubstantiatorState, AnalyzedChunk, ...], AnalyzedChunk],
    ) -> Callable[[ClaimSubstantiatorState, AnalyzedChunk, ...], AnalyzedChunk]:
        @wraps(func)
        async def wrapper(
            state: ClaimSubstantiatorState, chunk: AnalyzedChunk, *args, **kwargs
        ) -> AnalyzedChunk:
            try:
                return await func(state, chunk, *args, **kwargs)
            except Exception as e:
                func_logger = logging.getLogger(func.__module__)
                func_logger.error(
                    f"{operation_name} failed for chunk {chunk.chunk_index}: {str(e)}",
                    exc_info=True,
                )

                raise Exception(f"{operation_name} failed: {str(e)}") from e

        return wrapper

    return decorator


def register_node(name: str, description: str):
    """
    Decorator to register and control the execution of a workflow node with the workflow registry.

    - Registers the node with the agent registry.
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
        agent_registry.register(func.__name__, name, description)

        @wraps(func)
        async def wrapper(
            state: BaseWorkflowState, *args, **kwargs
        ) -> BaseWorkflowState:

            config = getattr(state, "config", None)
            project_id = getattr(config, "project_id", None)
            agents_to_run = getattr(config, "agents_to_run", None)

            if agents_to_run and func.__name__ not in agents_to_run:
                func_logger.info(
                    f"{func.__name__} ({project_id}): skipping (not in agents_to_run)"
                )
                return {}

            func_logger.info(f"{func.__name__} ({project_id}): starting")
            start_time = time.time()

            try:
                result = await func(state, *args, **kwargs)

            except Exception as e:
                func_logger.error(
                    f"{func.__name__} ({project_id}): workflow node execution failed with error: {str(e)}",
                    exc_info=True,
                )
                return {
                    "errors": [WorkflowError(task_name=func.__name__, error=str(e))]
                }

            func_logger.info(
                f"{func.__name__} ({project_id}): done in {time.time() - start_time:.2f} seconds"
            )

            return result

        return wrapper

    return decorator
