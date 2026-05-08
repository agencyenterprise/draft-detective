"""Unit tests for remove_fetch_result_for_file service function."""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.types import Overwrite

from lib.services.references import remove_fetch_result_for_file
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchConclusion,
    ReferenceFetchItem,
)
from lib.workflows.models import WorkflowRunType


def _make_fetch_item(
    file_id: str | None, conclusion: ReferenceFetchConclusion
) -> ReferenceFetchItem:
    return ReferenceFetchItem(
        reference_details="ref",
        reasoning="",
        source_url=None,
        file_id=file_id,
        final_conclusion=conclusion,
    )


def _make_state(results: list[ReferenceFetchResult]) -> ReferenceDownloaderState:
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER,
            project_id=str(uuid.uuid4()),
            references=[],
        ),
        fetched_references=results,
    )


def _make_run() -> MagicMock:
    run = MagicMock()
    run.langgraph_thread_id = str(uuid.uuid4())
    return run


@asynccontextmanager
async def _fake_checkpointer():
    yield MagicMock()


@pytest.fixture(autouse=True)
def _stub_persist_state():
    """Avoid hitting the DB when the references service mirrors state to state_json."""
    with patch(
        "lib.services.references.persist_workflow_run_state", new=AsyncMock()
    ) as m:
        yield m


@pytest.mark.asyncio
async def test_returns_zero_when_no_downloader_run_exists():
    with patch(
        "lib.services.references._get_downloader_workflow_state",
        new=AsyncMock(return_value=(None, None)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0


@pytest.mark.asyncio
async def test_returns_zero_when_state_has_no_fetched_references():
    state = _make_state([])

    with patch(
        "lib.services.references._get_downloader_workflow_state",
        new=AsyncMock(return_value=(_make_run(), state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0


@pytest.mark.asyncio
async def test_returns_zero_when_no_result_matches_file_id():
    other_file_id = str(uuid.uuid4())
    state = _make_state(
        [
            ReferenceFetchResult(
                reference_id="r1",
                input_reference="ref 1",
                status=ReferenceFetchStatus.COMPLETED,
                result=_make_fetch_item(
                    other_file_id, ReferenceFetchConclusion.SOURCE_FOUND
                ),
            )
        ]
    )

    aupdate_mock = AsyncMock()
    graph_app = MagicMock()
    graph_app.aupdate_state = aupdate_mock
    graph = MagicMock()
    graph.compile.return_value = graph_app

    with (
        patch(
            "lib.services.references._get_downloader_workflow_state",
            new=AsyncMock(return_value=(_make_run(), state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch("lib.services.references.create_graph", return_value=graph),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0
    aupdate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_removes_matching_entry_via_overwrite():
    target_file_id = str(uuid.uuid4())
    other_file_id = str(uuid.uuid4())
    keep = ReferenceFetchResult(
        reference_id="r_keep",
        input_reference="keep",
        status=ReferenceFetchStatus.COMPLETED,
        result=_make_fetch_item(other_file_id, ReferenceFetchConclusion.SOURCE_FOUND),
    )
    drop = ReferenceFetchResult(
        reference_id="r_drop",
        input_reference="drop",
        status=ReferenceFetchStatus.COMPLETED,
        result=_make_fetch_item(target_file_id, ReferenceFetchConclusion.SOURCE_FOUND),
    )
    state = _make_state([keep, drop])
    run = _make_run()

    aupdate_mock = AsyncMock()
    graph_app = MagicMock()
    graph_app.aupdate_state = aupdate_mock
    graph = MagicMock()
    graph.compile.return_value = graph_app

    with (
        patch(
            "lib.services.references._get_downloader_workflow_state",
            new=AsyncMock(return_value=(run, state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch(
            "lib.services.references.create_graph", return_value=graph
        ) as create_graph_mock,
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 1
    create_graph_mock.assert_called_once_with(WorkflowRunType.REFERENCE_DOWNLOADER)
    aupdate_mock.assert_awaited_once()
    call_args = aupdate_mock.await_args
    assert call_args.args[0] == {"configurable": {"thread_id": run.langgraph_thread_id}}
    state_update = call_args.args[1]
    overwrite_value = state_update["fetched_references"]
    # The reducer must be bypassed — Overwrite is the only way to remove entries.
    assert isinstance(overwrite_value, Overwrite)
    assert list(overwrite_value.value) == [keep]
    assert call_args.kwargs["as_node"] == "cleanup_failed_resources"


@pytest.mark.asyncio
async def test_removes_multiple_entries_pointing_at_same_file():
    target_file_id = str(uuid.uuid4())
    dup_a = ReferenceFetchResult(
        reference_id="ra",
        input_reference="a",
        status=ReferenceFetchStatus.COMPLETED,
        result=_make_fetch_item(target_file_id, ReferenceFetchConclusion.SOURCE_FOUND),
    )
    dup_b = ReferenceFetchResult(
        reference_id="rb",
        input_reference="b",
        status=ReferenceFetchStatus.COMPLETED,
        result=_make_fetch_item(target_file_id, ReferenceFetchConclusion.SOURCE_FOUND),
    )
    state = _make_state([dup_a, dup_b])

    aupdate_mock = AsyncMock()
    graph_app = MagicMock()
    graph_app.aupdate_state = aupdate_mock
    graph = MagicMock()
    graph.compile.return_value = graph_app

    with (
        patch(
            "lib.services.references._get_downloader_workflow_state",
            new=AsyncMock(return_value=(_make_run(), state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch("lib.services.references.create_graph", return_value=graph),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 2
    overwrite_value = aupdate_mock.await_args.args[1]["fetched_references"]
    assert list(overwrite_value.value) == []


@pytest.mark.asyncio
async def test_preserves_entries_without_result():
    """PENDING / ERROR entries have `result=None` and must never be filtered out."""
    target_file_id = str(uuid.uuid4())
    pending = ReferenceFetchResult(
        reference_id="pending",
        input_reference="pending",
        status=ReferenceFetchStatus.PENDING,
        result=None,
    )
    errored = ReferenceFetchResult(
        reference_id="errored",
        input_reference="errored",
        status=ReferenceFetchStatus.ERROR,
        result=None,
        error="boom",
    )
    drop = ReferenceFetchResult(
        reference_id="drop",
        input_reference="drop",
        status=ReferenceFetchStatus.COMPLETED,
        result=_make_fetch_item(target_file_id, ReferenceFetchConclusion.SOURCE_FOUND),
    )
    state = _make_state([pending, errored, drop])

    aupdate_mock = AsyncMock()
    graph_app = MagicMock()
    graph_app.aupdate_state = aupdate_mock
    graph = MagicMock()
    graph.compile.return_value = graph_app

    with (
        patch(
            "lib.services.references._get_downloader_workflow_state",
            new=AsyncMock(return_value=(_make_run(), state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch("lib.services.references.create_graph", return_value=graph),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 1
    overwrite_value = aupdate_mock.await_args.args[1]["fetched_references"]
    assert list(overwrite_value.value) == [pending, errored]
