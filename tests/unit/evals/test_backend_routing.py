"""Endpoint isolation without live servers, credentials, or model calls."""

import asyncio
import base64
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageUser

from evals_inspectai.common import api_client, api_solver
from evals_inspectai.common.backend import local_backend_for, resolve_base_url
from evals_inspectai.common.peer_review_fixture import (
    ReviewerMemo,
    run_review_assistant_workflow,
    setup_peer_review_project,
)


def test_remote_is_default_and_local_is_explicit(monkeypatch):
    from evals_inspectai.common import local_backend

    local = SimpleNamespace(ensure_started=AsyncMock())
    factory = Mock(return_value=local)
    monkeypatch.setattr(local_backend, "LocalBackend", factory)
    assert local_backend_for() is None
    assert local_backend_for("remote", "https://deployment.test") is None
    factory.assert_not_called()
    with pytest.raises(ValueError, match="backend must"):
        local_backend_for("typo")
    with pytest.raises(ValueError, match="cannot be combined"):
        local_backend_for("local", "https://deployment.test")
    assert local_backend_for("local") is local
    factory.assert_called_once_with()
    local.ensure_started.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_precedence(monkeypatch):
    monkeypatch.setenv("EVAL_API_BASE_URL", "https://environment.test")
    assert await resolve_base_url(None, None) == "https://environment.test"
    assert (
        await resolve_base_url(None, "https://explicit.test") == "https://explicit.test"
    )
    local = SimpleNamespace(ensure_started=AsyncMock(return_value="http://local.test"))
    assert await resolve_base_url(local, None) == "http://local.test"
    assert os.environ["EVAL_API_BASE_URL"] == "https://environment.test"
    with pytest.raises(ValueError, match="cannot be combined"):
        await resolve_base_url(local, "https://explicit.test")
    monkeypatch.delenv("EVAL_API_BASE_URL")
    assert await resolve_base_url(None, None) == api_client.DEFAULT_BASE_URL


@pytest.fixture
def fake_api(monkeypatch):
    requests = []

    async def respond(request):
        # Force the concurrent solvers to interleave between HTTP requests.
        await asyncio.sleep(0)
        requests.append(request)
        host, path = request.url.host, request.url.path
        body = (
            json.loads(request.content)
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        if "project_id" in body:
            assert body["project_id"] == host
        if path == "/api/projects":
            return httpx.Response(200, json={"project": {"id": host}})
        if path == "/tus":
            metadata = dict(
                item.split(" ", 1)
                for item in request.headers["Upload-Metadata"].split(",")
            )
            assert base64.b64decode(metadata["project_id"]).decode() == host
            return httpx.Response(201, headers={"Location": f"https://{host}/upload"})
        if path.startswith("/api/project/"):
            assert path.split("/")[3] == host
            if path.endswith("/revisions"):
                return httpx.Response(200, json={"revision": 2})
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "run": {"type": workflow, "status": "completed"},
                            "state": {"served_by": host},
                        }
                        for workflow in ("test_workflow", "document_processing")
                    ]
                },
            )
        if path == "/api/workflows/start":
            return httpx.Response(200, json={"workflow_run_id": host})
        if path.startswith("/api/workflows/") and request.method == "GET":
            assert path.split("/")[3] == host
            return httpx.Response(
                200, json={"run": {"status": "completed"}, "state": {}}
            )
        if path.startswith("/api/projects/"):
            assert path.split("/")[3] == host
        assert path in {"/upload", "/api/workflows/start-multiple"} or path.endswith(
            "/approve"
        )
        return httpx.Response(200, json={})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    monkeypatch.setenv("EVAL_API_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        api_solver, "transcript", lambda: SimpleNamespace(info=lambda _: None)
    )
    return requests


@pytest.mark.asyncio
@pytest.mark.parametrize("file_input", [False, True])
async def test_concurrent_agents_keep_their_own_endpoint(
    monkeypatch, fake_api, tmp_path, file_input
):
    monkeypatch.setenv("EVAL_API_BASE_URL", "https://environment.test")
    document = tmp_path / "document.md"
    document.write_text("test document")
    factory = (
        api_solver.api_workflow_agent_file
        if file_input
        else api_solver.api_workflow_agent
    )
    local = SimpleNamespace(ensure_started=AsyncMock(return_value="http://local.test"))
    agents = [
        factory("test_workflow", local_backend=local),
        factory("test_workflow", api_base_url="https://explicit.test"),
        factory("test_workflow"),
    ]
    results = await asyncio.gather(
        *[
            agent(
                AgentState(
                    messages=[
                        ChatMessageUser(
                            content=str(document) if file_input else "document"
                        )
                    ]
                )
            )
            for agent in agents
        ]
    )
    assert [
        json.loads(result.output.completion)["served_by"] for result in results
    ] == ["local.test", "explicit.test", "environment.test"]
    assert os.environ["EVAL_API_BASE_URL"] == "https://environment.test"
    assert len([r for r in fake_api if r.url.path == "/tus"]) == 3


@pytest.mark.asyncio
async def test_multistep_helpers_forward_endpoint(monkeypatch, fake_api):
    monkeypatch.setenv("EVAL_API_BASE_URL", "https://wrong.test")
    endpoint = "https://explicit.test"
    project = await setup_peer_review_project(
        "draft",
        [ReviewerMemo("memo.md", "memo")],
        revised_draft="revision",
        base_url=endpoint,
    )
    await run_review_assistant_workflow(project, "test_workflow", 1, base_url=endpoint)
    await api_client.create_project_and_start_workflows(
        "main",
        ["test_workflow"],
        supporting_files=[("support.md", "support")],
        publication_date="2026-01-01",
        base_url=endpoint,
    )
    await api_client.poll_until_status(
        project, "test_workflow", {"completed"}, base_url=endpoint
    )
    await api_client.approve_project_gate(project, base_url=endpoint)
    await api_client.link_reference_file(
        project, "reference", "file", base_url=endpoint
    )
    run_id = await api_client.start_workflow({"project_id": project}, base_url=endpoint)
    await api_client.get_workflow_state(run_id, base_url=endpoint)
    await api_client.poll_workflow_run_until_complete(run_id, base_url=endpoint)
    assert {r.url.host for r in fake_api} == {"explicit.test"}
