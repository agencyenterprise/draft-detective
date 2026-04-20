"""Diagnostic test to verify decorator receives runtime with context."""

import uuid
from unittest.mock import Mock, patch

import pytest

from lib.workflows.decorators import register_node

WORKFLOW_RUN_ID = str(uuid.uuid4())
PROGRESS_ID = uuid.uuid4()


@pytest.mark.asyncio
@patch("lib.workflows.decorators.get_or_create_progress", return_value=PROGRESS_ID)
@patch("lib.workflows.decorators.increment_and_complete_if_done", return_value=True)
@patch("lib.services.workflow_runs.get_workflow_run_status", return_value=None)
async def test_decorator_receives_runtime_with_context(
    mock_get_status, mock_increment, mock_get_or_create
):
    """Verify that the decorator correctly receives runtime with context attribute."""
    received_args = {}

    @register_node("Test Node")
    async def test_node(state, runtime):
        received_args["state"] = state
        received_args["runtime"] = runtime
        received_args["has_context"] = hasattr(runtime, "context")
        received_args["workflow_run_id"] = getattr(
            getattr(runtime, "context", None), "workflow_run_id", None
        )
        return {"result": "success"}

    mock_state = Mock()
    mock_state.config = Mock()
    mock_state.config.project_id = "test-project"

    mock_runtime = Mock()
    mock_runtime.context = Mock()
    mock_runtime.context.workflow_run_id = WORKFLOW_RUN_ID

    result = await test_node(mock_state, mock_runtime)

    assert received_args["state"] == mock_state
    assert received_args["runtime"] == mock_runtime
    assert received_args["has_context"] is True
    assert received_args["workflow_run_id"] == WORKFLOW_RUN_ID
    assert result == {"result": "success"}
