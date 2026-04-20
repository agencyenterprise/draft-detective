"""Unit tests for progress tracking flow - isolated layer testing."""

import uuid
from unittest.mock import Mock, patch
import pytest

from lib.models.workflow_progress import ProgressLevel
from lib.workflows.decorators import register_node


class TestDecoratorProgressTracking:
    """Test that the decorator creates and completes progress entries."""

    @pytest.mark.asyncio
    @patch("lib.workflows.decorators.get_or_create_progress")
    @patch("lib.workflows.decorators.increment_and_complete_if_done")
    async def test_decorator_creates_progress_on_node_execution(
        self, mock_increment, mock_get_or_create
    ):
        """Test that decorator creates progress when a node executes."""
        # Setup - workflow_run_id is stored as STRING in context
        workflow_run_id_str = str(uuid.uuid4())
        progress_id = uuid.uuid4()
        mock_get_or_create.return_value = progress_id
        mock_increment.return_value = True  # Indicates batch completed

        # Create a test node
        @register_node("Test Node")
        async def test_node(state, runtime):
            return {"result": "success"}

        # Create mock runtime with workflow_run_id (STRING, as it is in real context)
        mock_runtime = Mock()
        mock_runtime.context.workflow_run_id = workflow_run_id_str

        # Execute node
        mock_state = Mock()
        mock_state.config = Mock()
        mock_state.config.project_id = "test-project"
        result = await test_node(mock_state, mock_runtime)

        # Verify progress was created with UUID (converted from string)
        mock_get_or_create.assert_called_once()
        call_kwargs = mock_get_or_create.call_args[1]
        assert isinstance(call_kwargs["workflow_run_id"], uuid.UUID)
        assert str(call_kwargs["workflow_run_id"]) == workflow_run_id_str
        assert call_kwargs["name"] == "Test Node"
        assert call_kwargs["level"] == ProgressLevel.NODE

        # Verify progress was incremented (and completed since it returned True)
        mock_increment.assert_called_once_with(progress_id)


class TestRunTasksProgressTracking:
    """Test that run_tasks updates progress via contextvar."""

    @pytest.mark.asyncio
    async def test_run_tasks_updates_progress_via_contextvar(self):
        """Test that run_tasks reads progress_id from contextvar and updates progress."""
        from lib.run_utils import run_tasks
        from lib.workflows.context import current_progress_id

        progress_id = uuid.uuid4()
        update_calls = []

        # Set up contextvar with progress_id
        token = current_progress_id.set(progress_id)

        try:
            # Patch update_progress to capture calls
            with patch("lib.services.workflow_progress.update_progress") as mock_update:
                mock_update.side_effect = lambda pid, **kwargs: update_calls.append(
                    (pid, kwargs)
                )

                # Create simple async tasks
                async def task1():
                    return "result1"

                async def task2():
                    return "result2"

                tasks = [task1(), task2()]

                # Execute
                results, errors = await run_tasks(tasks, desc="Test tasks")

                # Verify task results
                assert results == ["result1", "result2"]
                assert errors == [None, None]

                # Verify progress was updated
                # With 2 tasks, we expect:
                # 1. Initial update with total_steps=2
                # 2. Progress update after each task completion (current_step=1, then 2)
                assert (
                    len(update_calls) >= 2
                ), f"Expected at least 2 progress updates, got {len(update_calls)}"

                # Verify all updates used the correct progress_id
                for call_progress_id, _ in update_calls:
                    assert call_progress_id == progress_id
        finally:
            current_progress_id.reset(token)

    @pytest.mark.asyncio
    async def test_run_tasks_works_without_progress_context(self):
        """Test that run_tasks works fine when no progress_id is set."""
        from lib.run_utils import run_tasks

        # Create simple async tasks
        async def task1():
            return "result1"

        async def task2():
            return "result2"

        tasks = [task1(), task2()]

        # Execute without setting contextvar - should work fine
        results, errors = await run_tasks(tasks, desc="Test tasks")

        # Verify results
        assert results == ["result1", "result2"]
        assert errors == [None, None]
