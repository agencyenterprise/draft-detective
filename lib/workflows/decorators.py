"""Workflow decorators for consistent behavior across nodes."""

import logging
from functools import wraps
from typing import Callable, TypeVar

from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)

# Type variable for decorator return types
T = TypeVar("T")


def requires_agent(agent_type: str):
    """
    Decorator to skip workflow node if agent not in agents_to_run configuration.

    Args:
        agent_type: The agent type string to check (e.g., "claims", "citations")

    Returns:
        Decorator that wraps async workflow node functions

    Example:
        @requires_agent("claims")
        async def extract_claims(state: ClaimSubstantiatorState) -> ClaimSubstantiatorState:
            ...
    """

    def decorator(
        func: Callable[[ClaimSubstantiatorState, ...], T],
    ) -> Callable[[ClaimSubstantiatorState, ...], T]:
        @wraps(func)
        async def wrapper(state: ClaimSubstantiatorState, *args, **kwargs) -> T:
            agents_to_run = state.config.agents_to_run
            if agents_to_run and agent_type not in agents_to_run:
                logger.info(
                    f"{func.__name__} ({state.config.session_id}): "
                    f"Skipping (agent '{agent_type}' not in agents_to_run)"
                )
                return {}  # type: ignore
            return await func(state, *args, **kwargs)

        return wrapper

    return decorator


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


def handle_workflow_node_errors():
    """
    Decorator for consistent workflow node error handling.

    Catches exceptions during workflow node execution, logs them with context,
    and update the state with a WorkflowError object.
    """

    def decorator(
        func: Callable[[ClaimSubstantiatorState, ...], ClaimSubstantiatorState],
    ) -> Callable[[ClaimSubstantiatorState, ...], ClaimSubstantiatorState]:
        @wraps(func)
        async def wrapper(
            state: ClaimSubstantiatorState, *args, **kwargs
        ) -> ClaimSubstantiatorState:
            try:
                return await func(state, *args, **kwargs)
            except Exception as e:
                func_logger = logging.getLogger(func.__module__)
                func_logger.error(
                    f"{func.__name__} workflow node execution failed with error: {str(e)}",
                    exc_info=True,
                )
                return {
                    "errors": [WorkflowError(task_name=func.__name__, error=str(e))]
                }

        return wrapper

    return decorator
