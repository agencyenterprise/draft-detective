"""Error utilities for Inspect AI eval solvers.

Provides a custom exception and checker to surface workflow-level errors
(e.g. rate-limit 429s, timeouts) as Inspect AI sample errors rather than
letting them be silently scored as INCORRECT.
"""

from typing import Any


class WorkflowCompletionError(Exception):
    """Raised when a completed workflow contains errors in its state.

    When this exception propagates during an Inspect AI eval, the framework
    records it as ``EvalSample.error`` and excludes the sample from score
    metrics — making completion errors visually distinct from genuine
    scoring misses.
    """


def check_workflow_errors(workflow_state: dict[str, Any]) -> None:
    """Raise if the workflow state contains any errors.

    Inspects the ``errors`` list present on every workflow state (inherited
    from ``BaseWorkflowState``).  Each entry is a ``WorkflowError`` dict
    with at least a ``task_name`` and ``error`` field.

    Args:
        workflow_state: The deserialized workflow state dict.

    Raises:
        WorkflowCompletionError: If one or more errors are present.
    """
    errors = workflow_state.get("errors", [])
    if not errors:
        return

    messages = []
    for entry in errors:
        if isinstance(entry, dict):
            task = entry.get("task_name", "unknown")
            error = entry.get("error", "unknown error")
            messages.append(f"{task}: {error}")

    raise WorkflowCompletionError(
        f"Workflow completed with {len(messages)} error(s): "
        + "; ".join(messages)
    )
