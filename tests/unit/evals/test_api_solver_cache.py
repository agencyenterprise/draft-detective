from pathlib import Path
import asyncio
import json
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageUser

from evals_inspectai.common import api_solver
from evals_inspectai.common.api_solver import _workflow_cache_key
from evals_inspectai.common.errors import WorkflowCompletionError


def test_workflow_cache_key_isolated_by_epoch():
    document = Path("/tmp/example.docx")

    assert _workflow_cache_key(document, 1) != _workflow_cache_key(document, 2)


@pytest.mark.asyncio
async def test_samples_share_only_within_the_same_epoch(monkeypatch, tmp_path):
    document = tmp_path / "example.docx"
    document.write_bytes(b"test fixture")
    epoch = ContextVar("test_epoch", default=1)
    monkeypatch.setattr(
        api_solver,
        "sample_active",
        lambda: SimpleNamespace(epoch=epoch.get(), eval_id="eval-1"),
    )
    starts = []

    async def start(**kwargs):
        await asyncio.sleep(0)
        starts.append((epoch.get(), kwargs["base_url"]))
        return str(epoch.get())

    async def poll(**kwargs):
        await asyncio.sleep(0)
        return {"state": {"extraction_epoch": kwargs["project_id"]}}

    monkeypatch.setattr(api_solver, "create_project_and_start_workflows", start)
    monkeypatch.setattr(api_solver, "poll_until_complete", poll)
    agent = api_solver.api_workflow_agent_file_cached(
        "test", {}, api_base_url="https://explicit.test"
    )

    async def sample(number):
        token = epoch.set(number)
        try:
            result = await agent(
                AgentState(messages=[ChatMessageUser(content=str(document))])
            )
            return json.loads(result.output.completion)["extraction_epoch"]
        finally:
            epoch.reset(token)

    epochs = [number for number in (1, 2, 3) for _ in range(21)]
    results = await asyncio.gather(*(sample(number) for number in epochs))
    assert results == list(map(str, epochs))
    assert sorted(starts) == [(number, "https://explicit.test") for number in (1, 2, 3)]


@pytest.mark.asyncio
async def test_failed_extraction_is_not_cached(monkeypatch, tmp_path):
    document = tmp_path / "example.docx"
    document.write_bytes(b"test fixture")
    monkeypatch.setattr(
        api_solver, "sample_active", lambda: SimpleNamespace(epoch=1, eval_id="eval-1")
    )
    start = AsyncMock(return_value="project")
    poll = AsyncMock(
        side_effect=[WorkflowCompletionError("failed"), {"state": {"ok": True}}]
    )
    monkeypatch.setattr(api_solver, "create_project_and_start_workflows", start)
    monkeypatch.setattr(api_solver, "poll_until_complete", poll)
    cache = {}
    agent = api_solver.api_workflow_agent_file_cached("test", cache)

    def state():
        return AgentState(messages=[ChatMessageUser(content=str(document))])

    with pytest.raises(WorkflowCompletionError):
        await agent(state())
    assert cache == {}
    result = await agent(state())
    assert json.loads(result.output.completion) == {"ok": True}
    assert start.await_count == 2


@pytest.mark.asyncio
async def test_new_eval_is_fresh_and_sibling_messages_are_independent(
    monkeypatch, tmp_path
):
    document = tmp_path / "example.md"
    document.write_text("AI")
    active = SimpleNamespace(epoch=1, eval_id="first")
    monkeypatch.setattr(api_solver, "sample_active", lambda: active)
    start = AsyncMock(return_value="project")
    poll = AsyncMock(
        return_value={
            "state": {"messages": [{"role": "assistant", "content": "original"}]}
        }
    )
    monkeypatch.setattr(api_solver, "create_project_and_start_workflows", start)
    monkeypatch.setattr(api_solver, "poll_until_complete", poll)
    agent = api_solver.api_workflow_agent_file_cached("test", {})

    def state():
        return AgentState(messages=[ChatMessageUser(content=str(document))])

    first = await agent(state())
    first.messages[0].content = "changed"
    second = await agent(state())
    assert second.messages[0].text == "original"
    assert start.await_count == 1
    active.eval_id = "second"
    await agent(state())
    assert start.await_count == 2
