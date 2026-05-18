"""Unit tests for remove_file_from_references service function."""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.references import remove_file_from_references
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)
from lib.workflows.models import WorkflowRunType


def _make_state(matches: list[ReferenceFileMatch]) -> ReferenceFileMatchingState:
    return ReferenceFileMatchingState(
        type=WorkflowRunType.REFERENCE_FILE_MATCHING,
        config=ReferenceFileMatchingConfig(project_id=str(uuid.uuid4())),
        file_id=str(uuid.uuid4()),
        supporting_file_ids=[],
        matches=matches,
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
async def test_returns_empty_when_no_workflow_run():
    with patch(
        "lib.services.references._get_file_matching_workflow_state",
        new=AsyncMock(return_value=(None, None)),
    ):
        removed = await remove_file_from_references(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == []


@pytest.mark.asyncio
async def test_returns_empty_when_no_state():
    with patch(
        "lib.services.references._get_file_matching_workflow_state",
        new=AsyncMock(return_value=(_make_run(), None)),
    ):
        removed = await remove_file_from_references(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == []


@pytest.mark.asyncio
async def test_returns_empty_when_no_match_for_file_id():
    other_file_id = str(uuid.uuid4())
    state = _make_state(
        [
            ReferenceFileMatch(
                reference_id="r1",
                file_id=other_file_id,
                source=MatchSource.AUTO_MATCHED,
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
            "lib.services.references._get_file_matching_workflow_state",
            new=AsyncMock(return_value=(_make_run(), state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch("lib.services.references.create_graph", return_value=graph),
    ):
        removed = await remove_file_from_references(
            str(uuid.uuid4()), str(uuid.uuid4()), revision=1
        )

    assert removed == []
    aupdate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_removes_single_match_and_preserves_others():
    target_file_id = str(uuid.uuid4())
    other_file_id = str(uuid.uuid4())
    keep = ReferenceFileMatch(
        reference_id="r_keep", file_id=other_file_id, source=MatchSource.AUTO_MATCHED
    )
    drop = ReferenceFileMatch(
        reference_id="r_drop", file_id=target_file_id, source=MatchSource.AUTO_MATCHED
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
            "lib.services.references._get_file_matching_workflow_state",
            new=AsyncMock(return_value=(run, state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch(
            "lib.services.references.create_graph", return_value=graph
        ) as create_graph_mock,
    ):
        removed = await remove_file_from_references(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert removed == ["r_drop"]
    create_graph_mock.assert_called_once_with(WorkflowRunType.REFERENCE_FILE_MATCHING)
    aupdate_mock.assert_awaited_once()
    call_args = aupdate_mock.await_args
    assert call_args.args[0] == {"configurable": {"thread_id": run.langgraph_thread_id}}
    assert call_args.args[1] == {"matches": [keep]}
    assert call_args.kwargs["as_node"] == "match_supporting_docs"


@pytest.mark.asyncio
async def test_removes_multiple_matches_pointing_at_same_file():
    target_file_id = str(uuid.uuid4())
    dup_a = ReferenceFileMatch(
        reference_id="ra", file_id=target_file_id, source=MatchSource.AUTO_MATCHED
    )
    dup_b = ReferenceFileMatch(
        reference_id="rb", file_id=target_file_id, source=MatchSource.AUTO_FETCHED
    )
    state = _make_state([dup_a, dup_b])

    aupdate_mock = AsyncMock()
    graph_app = MagicMock()
    graph_app.aupdate_state = aupdate_mock
    graph = MagicMock()
    graph.compile.return_value = graph_app

    with (
        patch(
            "lib.services.references._get_file_matching_workflow_state",
            new=AsyncMock(return_value=(_make_run(), state)),
        ),
        patch("lib.services.references.get_checkpointer", _fake_checkpointer),
        patch("lib.services.references.create_graph", return_value=graph),
    ):
        removed = await remove_file_from_references(
            str(uuid.uuid4()), target_file_id, revision=1
        )

    assert sorted(removed) == ["ra", "rb"]
    assert aupdate_mock.await_args.args[1] == {"matches": []}
