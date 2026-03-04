"""Diagnostic test to verify decorator receives runtime with context."""

from unittest.mock import Mock, patch

import pytest

from lib.workflows.decorators import register_node


@pytest.mark.asyncio
@patch("lib.workflows.decorators.get_or_create_progress")
@patch("lib.workflows.decorators.increment_and_complete_if_done")
async def test_decorator_receives_runtime_with_context(
    mock_increment, mock_get_or_create
):
    """Verify that the decorator correctly receives runtime with context attribute."""
    mock_get_or_create.return_value = None  # Disable progress tracking for this test

    # Track what the actual node function receives
    received_args = {}

    @register_node("Test Node", "Test description")
    async def test_node(state, runtime):
        received_args["state"] = state
        received_args["runtime"] = runtime
        received_args["has_context"] = hasattr(runtime, "context")
        received_args["workflow_run_id"] = getattr(
            getattr(runtime, "context", None), "workflow_run_id", None
        )
        return {"result": "success"}

    # Create mocks
    mock_state = Mock()
    mock_state.config = Mock()
    mock_state.config.project_id = "test-project"
    mock_state.config.agents_to_run = None

    mock_runtime = Mock()
    mock_runtime.context = Mock()
    mock_runtime.context.workflow_run_id = "test-workflow-id"

    # Execute the decorated function
    result = await test_node(mock_state, mock_runtime)

    # Verify the node received the arguments correctly
    assert received_args["state"] == mock_state
    assert received_args["runtime"] == mock_runtime
    assert received_args["has_context"] is True
    assert received_args["workflow_run_id"] == "test-workflow-id"
    assert result == {"result": "success"}
