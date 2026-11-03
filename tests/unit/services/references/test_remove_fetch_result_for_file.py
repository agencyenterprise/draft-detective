"""Unit tests for remove_fetch_result_for_file service function."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.references.service import remove_fetch_result_for_file
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchConclusion,
    ReferenceFetchItem,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)


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
    run.id = str(uuid.uuid4())
    run.langgraph_thread_id = str(uuid.uuid4())
    return run


@pytest.fixture(autouse=True)
def _stub_persist_state():
    """Capture the state_json write; the checkpointer write was removed in the
    write-side cutover, so persist_workflow_run_state is now the only write."""
    with patch(
        "lib.services.references.service.persist_workflow_run_state", new=AsyncMock()
    ) as m:
        yield m


@pytest.mark.asyncio
async def test_returns_zero_when_no_downloader_run_exists(_stub_persist_state):
    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(None, None)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0
    _stub_persist_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_returns_zero_when_state_has_no_fetched_references(_stub_persist_state):
    state = _make_state([])

    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(_make_run(), state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0
    _stub_persist_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_returns_zero_when_no_result_matches_file_id(_stub_persist_state):
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

    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(_make_run(), state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == 0
    _stub_persist_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_persists_filtered_state_dropping_matching_entry(_stub_persist_state):
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

    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(run, state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 1
    _stub_persist_state.assert_awaited_once()
    run_id_arg, persisted_state = _stub_persist_state.await_args.args
    assert run_id_arg == str(run.id)
    # Plain assignment of the filtered list bypasses the merge_fetch_results
    # reducer so the dropped entry is actually removed.
    assert persisted_state.fetched_references == [keep]


@pytest.mark.asyncio
async def test_removes_multiple_entries_pointing_at_same_file(_stub_persist_state):
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

    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(_make_run(), state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 2
    persisted_state = _stub_persist_state.await_args.args[1]
    assert persisted_state.fetched_references == []


@pytest.mark.asyncio
async def test_preserves_entries_without_result(_stub_persist_state):
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

    with patch(
        "lib.services.references.service.get_project_workflow_run_with_state",
        new=AsyncMock(return_value=(_make_run(), state)),
    ):
        removed = await remove_fetch_result_for_file(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == 1
    persisted_state = _stub_persist_state.await_args.args[1]
    assert persisted_state.fetched_references == [pending, errored]
