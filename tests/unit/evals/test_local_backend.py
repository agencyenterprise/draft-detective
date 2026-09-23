"""Lifecycle tests without starting servers, containers, or database connections."""

import asyncio
import subprocess
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from inspect_ai.model import get_model

from evals_inspectai.common import local_backend as module


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["database", "spawn", "health", "cancel"])
async def test_startup_failure_cleans_up_and_allows_retry(monkeypatch, tmp_path, stage):
    process = Mock()
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    database = AsyncMock()
    health = AsyncMock()
    monkeypatch.setattr(module, "_ensure_local_database", database)
    monkeypatch.setattr(module, "_free_port", lambda: 18765)
    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    backend = module.LocalBackend(model="openai/test", cwd=tmp_path)
    monkeypatch.setattr(backend, "_wait_for_health", health)
    failure = asyncio.CancelledError() if stage == "cancel" else RuntimeError("failed")
    failing = {
        "database": database,
        "spawn": spawn,
        "health": health,
        "cancel": health,
    }[stage]
    failing.side_effect = failure
    try:
        with pytest.raises(type(failure)):
            await backend.ensure_started()
        assert backend._url is None
        assert backend._process is None
        if stage in {"health", "cancel"}:
            process.terminate.assert_called_once()
        failing.side_effect = None
        assert (await backend.ensure_started()).startswith("http://127.0.0.1:")
        database.assert_awaited_with(ANY, tmp_path)
        assert spawn.call_args.kwargs["env"]["EVAL_WORKFLOW_MODEL"] == "openai/test"
        assert spawn.call_args.kwargs["env"]["MCP_ENABLED"] == "false"
        assert spawn.call_args.kwargs["stdout"].closed
        assert await backend.ensure_started() == backend._url
    finally:
        backend.shutdown()


def test_active_model_keeps_provider(monkeypatch):
    from inspect_ai.model import _model

    monkeypatch.setattr(_model, "active_model", lambda: get_model("mockllm/test"))
    assert module._active_model_name() == "mockllm/test"


@pytest.mark.asyncio
async def test_remote_database_never_starts_compose(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "_port_open", lambda *_: False)
    run = Mock()
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="non-local DATABASE_URL"):
        await module._ensure_local_database(
            {"DATABASE_URL": "postgresql://user@database.example/db"}, tmp_path
        )
    run.assert_not_called()


@pytest.mark.asyncio
async def test_database_uses_configured_directory_and_bounds_compose(
    monkeypatch, tmp_path
):
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://user@localhost/db\n")
    monkeypatch.setattr(module, "_port_open", Mock(side_effect=[False, True]))
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(module.subprocess, "run", run)
    await module._ensure_local_database({}, tmp_path)
    assert run.call_args.kwargs["cwd"] == tmp_path
    assert run.call_args.kwargs["timeout"] == 30


@pytest.mark.asyncio
async def test_does_not_silently_reuse_backend_for_different_model(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(module, "_active_model_name", lambda: "openai/new")
    backend = module.LocalBackend(cwd=tmp_path)
    backend._process = Mock()
    backend._process.poll.return_value = None
    backend._url = "http://127.0.0.1:8000"
    backend._started_model = "openai/old"
    try:
        with pytest.raises(ValueError, match="new LocalBackend"):
            await backend.ensure_started()
    finally:
        backend.shutdown()
