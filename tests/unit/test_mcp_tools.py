"""Unit tests for MCP tool functions with mocked service dependencies."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Patch auth factory before importing the MCP module (see test_mcp_server.py).
import lib.api.mcp_auth as _mcp_auth_mod

_orig = _mcp_auth_mod.create_mcp_auth
_mcp_auth_mod.create_mcp_auth = lambda: None

from lib.api.mcp import (  # noqa: E402
    _build_project_url,
    _resolve_user,
    create_project,
    get_project,
    run_workflow,
)

_mcp_auth_mod.create_mcp_auth = _orig


def _make_token(email: str = "alice@example.com", name: str = "Alice") -> MagicMock:
    token = MagicMock()
    token.claims = {"email": email, "name": name}
    return token


def _make_user(email: str = "alice@example.com", name: str = "Alice") -> MagicMock:
    user = MagicMock()
    user.email = email
    user.name = name
    user.id = uuid4()
    return user


# --- _build_project_url ---


def test_build_project_url():
    url = _build_project_url("abc-123")
    assert url.endswith("/projects/abc-123")
    assert not url.endswith("//projects/abc-123")


def test_build_project_url_strips_trailing_slash():
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.FRONTEND_URL = "https://app.example.com/"
        result = _build_project_url("proj-1")
    assert result == "https://app.example.com/projects/proj-1"


# --- _resolve_user ---


@pytest.mark.asyncio
async def test_resolve_user_calls_get_or_create():
    mock_user = _make_user()
    token = _make_token()

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="alice@example.com", name="Alice")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_raises_when_email_missing():
    token = MagicMock()
    token.claims = {"name": "No Email"}

    with pytest.raises(RuntimeError, match="Token missing 'email' claim"):
        await _resolve_user(token)


@pytest.mark.asyncio
async def test_resolve_user_falls_back_email_as_name():
    token = MagicMock()
    token.claims = {"email": "bob@example.com"}
    mock_user = _make_user(email="bob@example.com", name="bob@example.com")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="bob@example.com", name="bob@example.com")


# --- create_project ---


@pytest.mark.asyncio
async def test_create_project_returns_ids_and_url():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    file_record = MagicMock()
    file_record.id = uuid4()
    ctx = AsyncMock()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp.create_project_record",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "lib.api.mcp.finalize_file",
            new=AsyncMock(return_value=file_record),
        ),
    ):
        raw = await create_project(
            title="Test", content_markdown="# Hello", ctx=ctx, token=_make_token()
        )

    data = json.loads(raw)
    assert data["project_id"] == str(project.id)
    assert data["file_id"] == str(file_record.id)
    assert "/projects/" in data["project_url"]


@pytest.mark.asyncio
async def test_create_project_logs_context_info():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    ctx = AsyncMock()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.create_project_record", new=AsyncMock(return_value=project)),
        patch("lib.api.mcp.finalize_file", new=AsyncMock(return_value=MagicMock(id=uuid4()))),
    ):
        await create_project(
            title="T", content_markdown="md", ctx=ctx, token=_make_token()
        )

    ctx.info.assert_awaited_once()


# --- run_workflow ---


@pytest.mark.asyncio
async def test_run_workflow_rejects_invalid_type():
    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=_make_user())),
    ):
        with pytest.raises(ValueError, match="Unknown workflow_type 'nonexistent'"):
            await run_workflow(
                project_id="p1",
                workflow_types=["nonexistent"],
                token=_make_token(),
            )


@pytest.mark.asyncio
async def test_run_workflow_delegates_to_blocking_runner():
    user = _make_user()
    project_json = json.dumps({"id": "p1", "project_url": "http://x/projects/p1"})

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp.run_multiple_workflows_blocking", new=AsyncMock()
        ) as mock_run,
        patch(
            "lib.api.mcp._get_project_details_json",
            new=AsyncMock(return_value=project_json),
        ),
    ):
        result = await run_workflow(
            project_id="p1",
            workflow_types=["document_processing"],
            token=_make_token(),
        )

    mock_run.assert_awaited_once()
    assert json.loads(result)["id"] == "p1"


# --- get_project ---


@pytest.mark.asyncio
async def test_get_project_returns_details():
    user = _make_user()
    expected = json.dumps({"id": "p1", "title": "Test"})

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp._get_project_details_json",
            new=AsyncMock(return_value=expected),
        ) as mock_details,
    ):
        result = await get_project(project_id="p1", token=_make_token())

    from lib.models.project import AccessLevel

    mock_details.assert_awaited_once_with("p1", AccessLevel.READ, user)
    assert json.loads(result)["title"] == "Test"
