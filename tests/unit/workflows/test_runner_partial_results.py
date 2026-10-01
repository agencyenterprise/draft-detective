"""Partial results for fan-out workflows.

`run_workflow` streams both "values" and "updates" so each `Send` task's output
is persisted to state_json as soon as it finishes, not only once the whole
superstep completes. These tests drive a real LangGraph fan-out graph.
"""

import asyncio
import operator
from typing import Annotated, List
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langgraph.graph import StateGraph
from langgraph.types import Overwrite, Send

from lib.models.workflow_run import WorkflowRunType
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.context import ContextSchema
from lib.workflows.models import BaseWorkflowState
from lib.workflows.runner import run_workflow
from lib.workflows.state_updates import apply_node_update


class FanOutState(BaseWorkflowState):
    items: Annotated[List[int], operator.add] = []
    label: str = ""


def _build_fan_out_graph(release_rest: asyncio.Event) -> StateGraph:
    """Three parallel tasks; tasks 1 and 2 block until ``release_rest`` is set."""

    async def start(state: FanOutState) -> dict:
        return {"label": "started"}

    def fan_out(state: FanOutState) -> List[Send]:
        return [Send("work", {"i": i}) for i in range(3)]

    async def work(task: dict) -> dict:
        if task["i"] > 0:
            await release_rest.wait()
        return {"items": [task["i"]]}

    async def finish(state: FanOutState) -> dict:
        return {"label": "done"}

    graph = StateGraph(FanOutState)
    graph.add_node("start", start)
    # Send targets receive the Send payload, not the graph state.
    graph.add_node("work", work)  # type: ignore[arg-type]
    graph.add_node("finish", finish)
    graph.set_entry_point("start")
    graph.add_conditional_edges("start", fan_out)
    graph.add_edge("work", "finish")
    graph.set_finish_point("finish")
    return graph


@pytest.mark.asyncio
async def test_run_workflow_persists_each_fan_out_task_before_superstep_ends():
    workflow_run_id = str(uuid4())
    release_rest = asyncio.Event()
    persisted: List[FanOutState] = []

    async def record_persist(_run_id: str, state: FanOutState) -> None:
        persisted.append(state)
        # Only unblock the slower tasks once task 0's result has hit state_json:
        # if partial results weren't persisted, the run would hang here.
        if state.items == [0]:
            release_rest.set()

    with (
        patch("lib.workflows.runner.persist_workflow_run_state", new=record_persist),
        patch("lib.workflows.runner.get_workflow_manifest", return_value=None),
        patch("lib.workflows.runner.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.runner.fail_workflow_run", new=AsyncMock()),
        patch("lib.workflows.runner._persist_issues_from_state", new=AsyncMock()),
    ):
        final = await asyncio.wait_for(
            run_workflow(
                workflow_run_id=workflow_run_id,
                workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
                graph=_build_fan_out_graph(release_rest),
                state=FanOutState(),
                context=ContextSchema(
                    project_id=str(uuid4()),
                    workflow_run_id=workflow_run_id,
                    file_artifacts_service=MockFileArtifactsService(),
                ),
                thread_id=str(uuid4()),
            ),
            timeout=5,
        )

    assert isinstance(final, FanOutState)
    assert sorted(final.items) == [0, 1, 2]
    assert final.label == "done"
    # The "values" snapshot at the superstep boundary replaces the replayed
    # updates, so nothing is double-counted in any persisted state.
    assert all(len(s.items) == len(set(s.items)) for s in persisted)
    assert persisted[-1].items == final.items


def test_apply_node_update_uses_reducers_and_overwrites_plain_fields():
    state = FanOutState(items=[1], label="old")
    channels = StateGraph(FanOutState).channels

    updated = apply_node_update(
        state, {"items": [2], "label": "new", "unknown": 1}, channels
    )

    assert updated.items == [1, 2]
    assert updated.label == "new"
    assert state.items == [1]


def test_apply_node_update_honors_overwrite():
    state = FanOutState(items=[1, 2])
    channels = StateGraph(FanOutState).channels

    updated = apply_node_update(state, {"items": Overwrite([9])}, channels)

    assert updated.items == [9]
