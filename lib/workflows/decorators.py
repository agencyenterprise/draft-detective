"""Workflow decorators for consistent behavior across nodes."""

import logging
from functools import wraps
from typing import Callable, TypeVar

from lib.agents.registry import agent_registry
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.models import WorkflowError

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
            state: ClaimSubstantiatorState, chunk: DocumentChunk
        ) -> DocumentChunk:
            ...
    """

    def decorator(
        func: Callable[[ClaimSubstantiatorState, DocumentChunk, ...], DocumentChunk],
    ) -> Callable[[ClaimSubstantiatorState, DocumentChunk, ...], DocumentChunk]:
        @wraps(func)
        async def wrapper(
            state: ClaimSubstantiatorState, chunk: DocumentChunk, *args, **kwargs
        ) -> DocumentChunk:
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
        func: Callable[[ClaimSubstantiatorState, ...], ClaimSubstantiatorState],
    ) -> Callable[[ClaimSubstantiatorState, ...], ClaimSubstantiatorState]:

        func_logger = logging.getLogger(func.__module__)
        agent_registry.register(func.__name__, name, description)

        @wraps(func)
        async def wrapper(
            state: ClaimSubstantiatorState, *args, **kwargs
        ) -> ClaimSubstantiatorState:

            func_logger.info(f"{func.__name__} ({state.config.session_id}): starting")

            agents_to_run = state.config.agents_to_run
            if agents_to_run and func.__name__ not in agents_to_run:
                func_logger.info(
                    f"{func.__name__} ({state.config.session_id}): Skipping (not in agents_to_run)"
                )
                return {}

            try:
                result = await func(state, *args, **kwargs)

            except Exception as e:
                func_logger.error(
                    f"{func.__name__} ({state.config.session_id}): workflow node execution failed with error: {str(e)}",
                    exc_info=True,
                )
                return {
                    "errors": [WorkflowError(task_name=func.__name__, error=str(e))]
                }

            func_logger.info(f"{func.__name__} ({state.config.session_id}): done")

            return result

        return wrapper

    return decorator
