"""Unit tests for the runner's terminal-status branches.

`run_workflow` has four exit paths: success → COMPLETED, WorkflowCancelledError
→ on_cancel + leave CANCELLED, asyncio.TimeoutError → on_cancel + FAILED+timeout,
generic Exception → checkpoint append + FAILED+unhandled_exception. The wrapper
`run_workflow_with_dependency_check` adds a fifth: DependencyWaitTimeoutError
→ FAILED+dependency_timeout. These tests drive each branch with a mocked
graph/checkpointer so the behavior contract is locked in even though we don't
spin up real LangGraph.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from lib.models.workflow_run import WorkflowRunFailureReason, WorkflowRunType
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.context import ContextSchema
from lib.workflows.models import (
    BaseWorkflowState,
    DependencyWaitTimeoutError,
    WorkflowCancelledError,
)
from lib.workflows.runner import run_workflow, run_workflow_with_dependency_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_runner_db_helpers():
    """Stub the DB-touching helpers added for state_json dual-write so unit
    tests don't try to reach Postgres. Covers the per-yield persist, the
    error-mirror in the unhandled-exception branch, and the re-read+persist
    in the cancel/timeout branches' ``_mirror_post_cancel_state``.
    """
    with (
        patch("lib.workflows.runner.persist_workflow_run_state", new=AsyncMock()),
        patch(
            "lib.workflows.runner.get_workflow_run_state_by_thread_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        yield


def _make_context(project_id: str, workflow_run_id: str) -> ContextSchema:
    """Minimal ContextSchema — all the runner's terminal-branch logic only
    looks at project_id, so we don't need a real file artifacts service."""
    return ContextSchema(
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        file_artifacts_service=MockFileArtifactsService(),
    )


def _build_app_with_astream(astream_impl) -> MagicMock:
    """Build a mock CompiledStateGraph whose astream uses ``astream_impl``."""
    app = MagicMock()
    app.astream = astream_impl
    app.aget_state = AsyncMock(return_value=MagicMock(config={"configurable": {}}))
    app.aupdate_state = AsyncMock()
    return app


def _build_graph(app: MagicMock) -> MagicMock:
    """Build a mock StateGraph whose compile().with_config() returns ``app``."""
    graph = MagicMock()
    compiled = MagicMock()
    compiled.with_config.return_value = app
    graph.compile.return_value = compiled
    return graph


# ---------------------------------------------------------------------------
# run_workflow — terminal branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_success_marks_completed():
    """Success path writes COMPLETED via update_workflow_run_status, not fail_workflow_run."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    async def empty_astream(*_args, **_kwargs):
        # No iterations → completes immediately.
        return
        yield  # pragma: no cover — make this an async generator

    app = _build_app_with_astream(empty_astream)
    graph = _build_graph(app)
    fail = AsyncMock()
    update_status = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    manifest.on_cancel = AsyncMock()

    checkpointer_cm = MagicMock()
    checkpointer_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    checkpointer_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("lib.workflows.runner.get_checkpointer", return_value=checkpointer_cm),
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=update_status),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=graph,
            state=BaseWorkflowState(),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )

    fail.assert_not_awaited()
    manifest.on_cancel.assert_not_awaited()
    completed_calls = [
        c for c in update_status.await_args_list if c.args[1].value == "completed"
    ]
    assert len(completed_calls) == 1


@pytest.mark.asyncio
async def test_run_workflow_timeout_marks_failed_and_runs_on_cancel():
    """asyncio.TimeoutError triggers FAILED+timeout and invokes manifest.on_cancel."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    async def raising_astream(*_args, **_kwargs):
        raise asyncio.TimeoutError()
        yield  # pragma: no cover

    app = _build_app_with_astream(raising_astream)
    graph = _build_graph(app)
    fail = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    manifest.on_cancel = AsyncMock()

    checkpointer_cm = MagicMock()
    checkpointer_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    checkpointer_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("lib.workflows.runner.get_checkpointer", return_value=checkpointer_cm),
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=graph,
            state=BaseWorkflowState(),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )

    manifest.on_cancel.assert_awaited_once()
    fail.assert_awaited_once()
    args, kwargs = fail.await_args
    assert args[0] == workflow_run_id
    assert args[1] == project_id
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.TIMEOUT
    assert "max_duration" in kwargs["failure_message"]


@pytest.mark.asyncio
async def test_run_workflow_unhandled_exception_marks_failed_and_persists_to_checkpoint():
    """A bare Exception is captured into the checkpoint and the run becomes FAILED+unhandled_exception."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    async def raising_astream(*_args, **_kwargs):
        raise RuntimeError("boom in node")
        yield  # pragma: no cover

    app = _build_app_with_astream(raising_astream)
    graph = _build_graph(app)
    fail = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    manifest.on_cancel = AsyncMock()

    checkpointer_cm = MagicMock()
    checkpointer_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    checkpointer_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("lib.workflows.runner.get_checkpointer", return_value=checkpointer_cm),
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=graph,
            state=BaseWorkflowState(),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )

    # Error was appended to LangGraph checkpoint for observability
    app.aupdate_state.assert_awaited_once()
    update_args = app.aupdate_state.await_args.args
    assert "errors" in update_args[1]
    persisted_errors = update_args[1]["errors"]
    assert len(persisted_errors) == 1
    assert persisted_errors[0].error == "boom in node"
    assert persisted_errors[0].workflow_run_id == workflow_run_id

    fail.assert_awaited_once()
    kwargs = fail.await_args.kwargs
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.UNHANDLED_EXCEPTION
    assert kwargs["failure_message"] == "boom in node"


@pytest.mark.asyncio
async def test_run_workflow_cancelled_runs_on_cancel_without_failing():
    """WorkflowCancelledError invokes on_cancel but does NOT call fail_workflow_run."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    async def raising_astream(*_args, **_kwargs):
        raise WorkflowCancelledError("user cancelled")
        yield  # pragma: no cover

    app = _build_app_with_astream(raising_astream)
    graph = _build_graph(app)
    fail = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    manifest.on_cancel = AsyncMock()

    checkpointer_cm = MagicMock()
    checkpointer_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    checkpointer_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("lib.workflows.runner.get_checkpointer", return_value=checkpointer_cm),
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=graph,
            state=BaseWorkflowState(),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )

    manifest.on_cancel.assert_awaited_once()
    fail.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_workflow_with_dependency_check — dependency timeout branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dependency_wait_timeout_marks_failed_with_dependency_timeout_reason():
    """The wrapper translates DependencyWaitTimeoutError into FAILED+dependency_timeout."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_VALIDATION
    config.project_id = project_id

    fail = AsyncMock()

    with (
        patch(
            "lib.workflows.runner.wait_for_dependencies",
            new=AsyncMock(side_effect=DependencyWaitTimeoutError("waited too long")),
        ),
        patch(
            "lib.workflows.runner.run_workflow_from_config", new=AsyncMock()
        ) as mock_run,
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
    ):
        await run_workflow_with_dependency_check(
            config=config,
            thread_id=str(uuid4()),
            workflow_run_id=workflow_run_id,
            user=MagicMock(),
            revision=1,
        )

    # The actual workflow body never ran.
    mock_run.assert_not_awaited()

    fail.assert_awaited_once()
    args, kwargs = fail.await_args
    assert args[0] == workflow_run_id
    assert args[1] == project_id
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.DEPENDENCY_TIMEOUT
    assert "waited too long" in kwargs["failure_message"]


@pytest.mark.asyncio
async def test_dependency_check_wraps_unexpected_exceptions_into_failed():
    """Unexpected exceptions raised before run_workflow are caught and mapped to UNHANDLED_EXCEPTION."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_VALIDATION
    config.project_id = project_id

    fail = AsyncMock()

    with (
        patch(
            "lib.workflows.runner.wait_for_dependencies",
            new=AsyncMock(side_effect=RuntimeError("setup failure")),
        ),
        patch("lib.workflows.runner.run_workflow_from_config", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
    ):
        await run_workflow_with_dependency_check(
            config=config,
            thread_id=str(uuid4()),
            workflow_run_id=workflow_run_id,
            user=MagicMock(),
            revision=1,
        )

    fail.assert_awaited_once()
    kwargs = fail.await_args.kwargs
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.UNHANDLED_EXCEPTION
    assert kwargs["failure_message"] == "setup failure"


@pytest.mark.asyncio
async def test_dependency_check_swallows_workflow_cancelled_error():
    """WorkflowCancelledError leaving wait_for_dependencies does not call fail_workflow_run."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_VALIDATION
    config.project_id = project_id

    fail = AsyncMock()

    with (
        patch(
            "lib.workflows.runner.wait_for_dependencies",
            new=AsyncMock(side_effect=WorkflowCancelledError("dep cancelled")),
        ),
        patch("lib.workflows.runner.run_workflow_from_config", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
    ):
        await run_workflow_with_dependency_check(
            config=config,
            thread_id=str(uuid4()),
            workflow_run_id=workflow_run_id,
            user=MagicMock(),
            revision=1,
        )

    fail.assert_not_awaited()
