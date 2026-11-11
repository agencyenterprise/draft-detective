"""Unit tests for the runner's terminal-status branches.

`run_workflow` has four exit paths: success → COMPLETED, WorkflowCancelledError
→ on_cancel + leave CANCELLED, asyncio.TimeoutError → on_cancel + FAILED+timeout,
generic Exception → persist error to state_json + FAILED+unhandled_exception. The
wrapper `run_workflow_with_dependency_check` adds a fifth:
DependencyWaitTimeoutError → FAILED+dependency_timeout. These tests drive each
branch with a mocked graph so the behavior contract is locked in even though we
don't spin up real LangGraph.
"""

from typing import cast
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
from lib.workflows.runner import (
    run_workflow,
    run_workflow_from_config,
    run_workflow_with_dependency_check,
)
from lib.workflows.workflow_types import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_runner_db_helpers():
    """Stub the DB-touching persist helper so unit tests don't reach Postgres.
    Covers the per-yield persist, the error persist in the unhandled-exception
    branch, and the persist of on_cancel's returned state in the cancel/timeout
    branches.
    """
    with patch("lib.workflows.runner.persist_workflow_run_state", new=AsyncMock()):
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
    # on_cancel returns the cleaned-up state; echo the input state (not a bare mock).
    manifest.on_cancel = AsyncMock(side_effect=lambda state: state)

    with (
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
        raise TimeoutError()
        yield  # pragma: no cover

    app = _build_app_with_astream(raising_astream)
    graph = _build_graph(app)
    fail = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    # on_cancel returns the cleaned-up state; echo the input state (not a bare mock).
    manifest.on_cancel = AsyncMock(side_effect=lambda state: state)

    persist = AsyncMock()

    with (
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
        patch("lib.workflows.runner.persist_workflow_run_state", new=persist),
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
    # A run the reaper already failed keeps the reaper's cleanup.
    assert persist.await_args.kwargs == {"unless_failed": True}


@pytest.mark.asyncio
async def test_run_workflow_unhandled_exception_marks_failed_and_persists_error():
    """A bare Exception is persisted onto state_json and the run becomes FAILED+unhandled_exception."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    async def raising_astream(*_args, **_kwargs):
        raise RuntimeError("boom in node")
        yield  # pragma: no cover

    app = _build_app_with_astream(raising_astream)
    graph = _build_graph(app)
    fail = AsyncMock()
    persist = AsyncMock()

    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    # on_cancel returns the cleaned-up state; echo the input state (not a bare mock).
    manifest.on_cancel = AsyncMock(side_effect=lambda state: state)

    with (
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
        # Override the autouse stub so we can inspect the persisted error state.
        patch("lib.workflows.runner.persist_workflow_run_state", new=persist),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=graph,
            state=BaseWorkflowState(),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )

    # The error was captured onto state_json (the sole error-persistence path
    # now that the checkpointer is gone).
    persist.assert_awaited()
    persisted_run_id, persisted_state = persist.await_args.args
    assert persisted_run_id == workflow_run_id
    assert len(persisted_state.errors) == 1
    assert persisted_state.errors[0].error == "boom in node"
    assert persisted_state.errors[0].workflow_run_id == workflow_run_id

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
    # on_cancel returns the cleaned-up state; echo the input state (not a bare mock).
    manifest.on_cancel = AsyncMock(side_effect=lambda state: state)

    persist = AsyncMock()

    with (
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
        patch("lib.workflows.runner.persist_workflow_run_state", new=persist),
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
    # A user cancel is the runner's own to clean up.
    assert persist.await_args.kwargs == {"unless_failed": False}


# ---------------------------------------------------------------------------
# run_workflow_with_dependency_check — dependency timeout branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dependency_wait_timeout_marks_failed_with_dependency_timeout_reason():
    """The wrapper translates DependencyWaitTimeoutError into FAILED+dependency_timeout."""
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())

    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_VALIDATION_V2
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
    config.type = WorkflowRunType.REFERENCE_VALIDATION_V2
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
    config.type = WorkflowRunType.REFERENCE_VALIDATION_V2
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


# ---------------------------------------------------------------------------
# run_workflow_from_config — prior_self_state seeding
# ---------------------------------------------------------------------------


def _seeding_patches(get_latest, create_state):
    """Patch run_workflow_from_config's collaborators so only the seeding
    branch is exercised."""
    return (
        patch("lib.workflows.runner.create_graph", return_value=MagicMock()),
        patch("lib.workflows.runner.create_context", return_value=MagicMock()),
        patch(
            "lib.workflows.runner.get_latest_workflow_run_state_by_type", new=get_latest
        ),
        patch("lib.workflows.runner.create_state", new=create_state),
        patch("lib.workflows.runner.run_workflow", new=AsyncMock()),
        patch("lib.workflows.runner.propagate_attributes"),
    )


@pytest.mark.asyncio
async def test_run_workflow_from_config_seeds_prior_state_when_enabled():
    """Fresh runs read the prior same-type run's state (excluding themselves)
    and pass it to create_state."""
    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_DOWNLOADER
    config.project_id = "proj-1"

    prior = MagicMock()
    get_latest = AsyncMock(return_value=prior)
    create_state = AsyncMock()

    p1, p2, p3, p4, p5, p6 = _seeding_patches(get_latest, create_state)
    with p1, p2, p3, p4, p5, p6:
        await run_workflow_from_config(
            config=config,
            thread_id=str(uuid4()),
            workflow_run_id="run-1",
            user=MagicMock(),
            revision=3,
            seed_prior_state=True,
        )

    get_latest.assert_awaited_once_with(
        "proj-1", config.type, 3, exclude_run_id="run-1"
    )
    assert create_state.await_args.kwargs["prior_self_state"] is prior


@pytest.mark.asyncio
async def test_run_workflow_from_config_skips_seeding_on_resume():
    """Resumed runs (seed_prior_state=False) must not adopt another run's state."""
    config = MagicMock()
    config.type = WorkflowRunType.REFERENCE_DOWNLOADER
    config.project_id = "proj-1"

    get_latest = AsyncMock()
    create_state = AsyncMock()

    p1, p2, p3, p4, p5, p6 = _seeding_patches(get_latest, create_state)
    with p1, p2, p3, p4, p5, p6:
        await run_workflow_from_config(
            config=config,
            thread_id=str(uuid4()),
            workflow_run_id="run-1",
            user=MagicMock(),
            revision=3,
            seed_prior_state=False,
        )

    get_latest.assert_not_awaited()
    assert create_state.await_args.kwargs["prior_self_state"] is None


# ---------------------------------------------------------------------------
# run_workflow — a failing on_cancel hook is best-effort cleanup
# ---------------------------------------------------------------------------


def _raising_astream(exc: BaseException):
    async def astream(*_args, **_kwargs):
        raise exc
        yield  # pragma: no cover

    return astream


async def _run_with_failing_teardown(
    exc: BaseException, *, failing: str
) -> tuple[AsyncMock, MagicMock]:
    """Run a workflow whose stream raises ``exc`` while its teardown fails.

    ``failing`` names the step that raises: ``"hook"`` (on_cancel) or
    ``"persist"`` (the persist of the hook's returned state).
    """
    workflow_run_id = str(uuid4())
    project_id = str(uuid4())
    fail = AsyncMock()
    manifest = MagicMock()
    manifest.max_duration_seconds = 60
    if failing == "hook":
        manifest.on_cancel = AsyncMock(side_effect=RuntimeError("hook broke"))
        persist = AsyncMock()
    else:
        manifest.on_cancel = AsyncMock(side_effect=lambda state: state)
        persist = AsyncMock(side_effect=RuntimeError("db down"))

    with (
        patch("lib.workflows.runner.get_workflow_manifest", return_value=manifest),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=fail),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
        patch("lib.workflows.runner.persist_workflow_run_state", new=persist),
    ):
        await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=_build_graph(_build_app_with_astream(_raising_astream(exc))),
            state=cast(WorkflowState, BaseWorkflowState()),
            context=_make_context(project_id, workflow_run_id),
            thread_id=str(uuid4()),
        )
    return fail, manifest


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", ["hook", "persist"])
async def test_run_workflow_timeout_still_marks_timeout_when_teardown_fails(
    failing: str,
):
    """A failing on_cancel (or its persist) must not turn TIMEOUT into UNHANDLED_EXCEPTION."""
    fail, manifest = await _run_with_failing_teardown(TimeoutError(), failing=failing)

    manifest.on_cancel.assert_awaited_once()
    fail.assert_awaited_once()
    assert fail.await_args is not None
    assert fail.await_args.kwargs["failure_reason"] == WorkflowRunFailureReason.TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", ["hook", "persist"])
async def test_run_workflow_cancel_does_not_fail_run_when_teardown_fails(
    failing: str,
):
    """A failing on_cancel on the cancel path is logged; the run is not marked FAILED."""
    fail, manifest = await _run_with_failing_teardown(
        WorkflowCancelledError("user cancelled"), failing=failing
    )

    manifest.on_cancel.assert_awaited_once()
    fail.assert_not_awaited()
