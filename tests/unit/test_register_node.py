"""Unit tests for the register_node decorator."""

import uuid
from unittest.mock import Mock, call, patch

import pytest

from lib.models.workflow_run import WorkflowRunStatus
from lib.workflows.context import current_progress_id
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowCancelledError, WorkflowError

PROGRESS_ID = uuid.uuid4()
WORKFLOW_RUN_ID = str(uuid.uuid4())


def _make_runtime(workflow_run_id=WORKFLOW_RUN_ID, project_id="test-project"):
    runtime = Mock()
    runtime.context.workflow_run_id = workflow_run_id
    runtime.context.project_id = project_id
    return runtime


@pytest.fixture(autouse=True)
def patch_external_deps():
    """Patch all external I/O calls used by the decorator."""
    with (
        patch(
            "lib.workflows.decorators.get_or_create_progress",
            return_value=PROGRESS_ID,
        ),
        patch(
            "lib.workflows.decorators.increment_and_complete_if_done",
            return_value=False,
        ),
        patch(
            "lib.services.workflow_runs.get_workflow_run_status",
            return_value=WorkflowRunStatus.RUNNING,
        ),
    ):
        yield


class TestValidation:
    @pytest.mark.asyncio
    async def test_raises_when_workflow_run_id_is_none(self):
        """Decorator must raise ValueError before doing anything when workflow_run_id is absent."""

        @register_node("Test Node")
        async def test_node(state, runtime):
            return {}

        with pytest.raises(ValueError, match="Workflow run ID is not set"):
            await test_node(Mock(), _make_runtime(workflow_run_id=None))

    @pytest.mark.asyncio
    async def test_raises_when_workflow_run_id_is_empty_string(self):
        """Empty string is treated the same as missing."""

        @register_node("Test Node")
        async def test_node(state, runtime):
            return {}

        with pytest.raises(ValueError, match="Workflow run ID is not set"):
            await test_node(Mock(), _make_runtime(workflow_run_id=""))


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_exception_is_caught_and_returned_as_workflow_error(self):
        """Unhandled exception from the node must be returned as a WorkflowError dict."""

        @register_node("Test Node")
        async def failing_node(state, runtime):
            raise RuntimeError("something went wrong")

        result = await failing_node(Mock(), _make_runtime())

        assert "errors" in result
        assert len(result["errors"]) == 1
        error = result["errors"][0]
        assert isinstance(error, WorkflowError)

    @pytest.mark.asyncio
    async def test_workflow_error_fields_are_populated_correctly(self):
        """WorkflowError must carry the function name, message, and workflow_run_id."""

        @register_node("Test Node")
        async def failing_node(state, runtime):
            raise ValueError("bad input")

        result = await failing_node(Mock(), _make_runtime())

        error = result["errors"][0]
        assert error.task_name == "failing_node"
        assert "bad input" in error.error
        assert error.workflow_run_id == WORKFLOW_RUN_ID

    @pytest.mark.asyncio
    async def test_workflow_cancelled_error_is_reraised(self):
        """WorkflowCancelledError must propagate out rather than being swallowed."""

        @register_node("Test Node")
        async def test_node(state, runtime):
            return {}

        with (
            patch(
                "lib.services.workflow_runs.get_workflow_run_status",
                return_value=WorkflowRunStatus.CANCELLED,
            ),
        ):
            with pytest.raises(WorkflowCancelledError):
                await test_node(Mock(), _make_runtime())


class TestProgressFinallyBlock:
    @pytest.mark.asyncio
    async def test_progress_is_completed_after_successful_execution(self):
        """Progress must be incremented when the node finishes successfully."""

        @register_node("Test Node")
        async def test_node(state, runtime):
            return {"result": "ok"}

        with patch(
            "lib.workflows.decorators.increment_and_complete_if_done",
            return_value=False,
        ) as mock_increment:
            await test_node(Mock(), _make_runtime())

        mock_increment.assert_called_once_with(PROGRESS_ID)

    @pytest.mark.asyncio
    async def test_progress_is_completed_after_exception(self):
        """Finally block must complete progress even when the node raises."""

        @register_node("Test Node")
        async def failing_node(state, runtime):
            raise RuntimeError("boom")

        with patch(
            "lib.workflows.decorators.increment_and_complete_if_done",
            return_value=False,
        ) as mock_increment:
            await failing_node(Mock(), _make_runtime())

        mock_increment.assert_called_once_with(PROGRESS_ID)

    @pytest.mark.asyncio
    async def test_progress_is_completed_after_cancellation(self):
        """Finally block must complete progress even when the workflow is cancelled."""

        @register_node("Test Node")
        async def test_node(state, runtime):
            return {}

        with (
            patch(
                "lib.workflows.decorators.increment_and_complete_if_done",
                return_value=False,
            ) as mock_increment,
            patch(
                "lib.services.workflow_runs.get_workflow_run_status",
                return_value=WorkflowRunStatus.CANCELLED,
            ),
        ):
            with pytest.raises(WorkflowCancelledError):
                await test_node(Mock(), _make_runtime())

        mock_increment.assert_called_once_with(PROGRESS_ID)


class TestCancellationCheck:
    @pytest.mark.asyncio
    async def test_pre_execution_cancellation_prevents_node_from_running(self):
        """When already cancelled, the node function must never be called."""
        was_called = False

        @register_node("Test Node")
        async def test_node(state, runtime):
            nonlocal was_called
            was_called = True
            return {}

        with (
            patch(
                "lib.services.workflow_runs.get_workflow_run_status",
                return_value=WorkflowRunStatus.CANCELLED,
            ),
            pytest.raises(WorkflowCancelledError),
        ):
            await test_node(Mock(), _make_runtime())

        assert not was_called


class TestContextvarManagement:
    @pytest.mark.asyncio
    async def test_current_progress_id_is_set_during_node_execution(self):
        """current_progress_id contextvar must carry PROGRESS_ID while the node runs."""
        captured_id = None

        @register_node("Test Node")
        async def test_node(state, runtime):
            nonlocal captured_id
            captured_id = current_progress_id.get()
            return {}

        with patch(
            "lib.workflows.decorators.get_or_create_progress",
            return_value=PROGRESS_ID,
        ):
            await test_node(Mock(), _make_runtime())

        assert captured_id == PROGRESS_ID

    @pytest.mark.asyncio
    async def test_current_progress_id_is_reset_after_successful_execution(self):
        """contextvar must be restored to its previous value after the node finishes."""
        sentinel = uuid.uuid4()
        token = current_progress_id.set(sentinel)

        try:
            @register_node("Test Node")
            async def test_node(state, runtime):
                return {}

            await test_node(Mock(), _make_runtime())

            assert current_progress_id.get() == sentinel
        finally:
            current_progress_id.reset(token)

    @pytest.mark.asyncio
    async def test_current_progress_id_is_reset_after_exception(self):
        """contextvar must be restored even when the node raises an exception."""
        sentinel = uuid.uuid4()
        token = current_progress_id.set(sentinel)

        try:
            @register_node("Test Node")
            async def failing_node(state, runtime):
                raise RuntimeError("error")

            await failing_node(Mock(), _make_runtime())

            assert current_progress_id.get() == sentinel
        finally:
            current_progress_id.reset(token)


class TestDecoratorMetadata:
    def test_wraps_preserves_function_name(self):
        """@wraps must preserve the original function's __name__ for debugging."""

        @register_node("Test Node")
        async def my_custom_node(state, runtime):
            return {}

        assert my_custom_node.__name__ == "my_custom_node"

    def test_wraps_preserves_function_module(self):
        """@wraps must preserve the original function's __module__."""

        @register_node("Test Node")
        async def my_custom_node(state, runtime):
            return {}

        assert my_custom_node.__module__ == __name__
