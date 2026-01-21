"""Diagnostic tests for progress tracking - skipped by default.

These tests are debugging aids for development, not production tests.
Run them explicitly with: pytest -m diagnostic tests/unit/test_progress_diagnostic.py
"""

import inspect
import logging
import uuid
from unittest.mock import Mock, patch

import pytest

from lib.models.workflow_progress import ProgressLevel
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

# Mark all tests in this module as diagnostic (skipped by default)
pytestmark = pytest.mark.skip(reason="Diagnostic tests - run explicitly with -m diagnostic")


@pytest.mark.asyncio
@patch('lib.workflows.decorators.create_and_start_progress')
async def test_diagnostic_check_decorator_receives_workflow_run_id(mock_create):
    """Diagnostic: Check if decorator receives workflow_run_id correctly and converts string to UUID."""

    # Setup - this simulates how nodes are actually called
    # workflow_run_id is a STRING in context (as returned by create_workflow_run)
    workflow_run_id_str = str(uuid.uuid4())
    progress_id = uuid.uuid4()
    mock_create.return_value = progress_id

    # Create a test node
    @register_node("Diagnostic Node", "Testing progress tracking")
    async def test_node(state, runtime):
        return {"result": "success"}

    # Create properly structured mocks
    mock_state = Mock()
    mock_state.config = Mock()
    mock_state.config.project_id = "test-project"
    mock_state.config.agents_to_run = None  # Don't skip

    mock_runtime = Mock()
    mock_runtime.context = Mock()
    mock_runtime.context.workflow_run_id = workflow_run_id_str  # STRING, not UUID

    # Execute node
    await test_node(mock_state, mock_runtime)

    # Check if create_and_start_progress was called
    assert mock_create.called, "Progress tracking not triggered - workflow_run_id not detected"

    # Verify it was called with a UUID object (converted from string)
    called_workflow_run_id = mock_create.call_args[1]['workflow_run_id']
    assert isinstance(called_workflow_run_id, uuid.UUID)
    assert str(called_workflow_run_id) == workflow_run_id_str
    assert mock_create.call_args[1]['name'] == "Diagnostic Node"
    assert mock_create.call_args[1]['level'] == ProgressLevel.NODE


@pytest.mark.asyncio
async def test_diagnostic_check_real_node_signature():
    """Diagnostic: Check a real node to see its actual signature."""
    from lib.workflows.claim_extraction.nodes.extract_claims import extract_claims

    sig = inspect.signature(extract_claims)
    params = list(sig.parameters.keys())

    # Check if it matches our expectations
    assert len(params) == 2, f"Expected 2 params, got {len(params)}"
    assert params[0] == "state", f"First param should be 'state', got '{params[0]}'"
    assert params[1] == "runtime", f"Second param should be 'runtime', got '{params[1]}'"


@pytest.mark.asyncio
@patch('lib.workflows.decorators.create_and_start_progress', side_effect=Exception("TEST: This should be caught"))
async def test_diagnostic_check_error_handling(mock_create):
    """Diagnostic: Check if progress tracking errors are handled gracefully."""

    workflow_run_id = str(uuid.uuid4())

    @register_node("Error Test Node", "Testing error handling")
    async def test_node(state, runtime):
        return {"result": "success"}

    # Create mocks
    mock_state = Mock()
    mock_state.config = Mock()
    mock_state.config.project_id = None
    mock_state.config.agents_to_run = None

    mock_runtime = Mock()
    mock_runtime.context = Mock()
    mock_runtime.context.workflow_run_id = workflow_run_id

    # Execute node - should NOT fail even though progress creation fails
    result = await test_node(mock_state, mock_runtime)

    # Check that the node still executed successfully
    assert result == {"result": "success"}

