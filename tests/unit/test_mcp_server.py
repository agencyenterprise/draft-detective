"""Tests for MCP server tool registration and list_workflow_types using FastMCP Client.

Follows the testing best practices from https://gofastmcp.com/servers/testing,
using pytest-asyncio fixtures with the FastMCP Client for in-memory testing.
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Patch auth factory before importing the MCP module.
# lib.api.mcp calls create_mcp_auth() at module level, which raises
# RuntimeError in test environments without OAuth credentials.
import lib.api.mcp_auth as _mcp_auth_mod

_orig_create_mcp_auth = _mcp_auth_mod.create_mcp_auth
_mcp_auth_mod.create_mcp_auth = lambda: None

from lib.api.mcp import mcp  # noqa: E402

_mcp_auth_mod.create_mcp_auth = _orig_create_mcp_auth

from fastmcp.client import Client  # noqa: E402
from fastmcp.server.auth import AccessToken  # noqa: E402
from fastmcp.server.dependencies import _task_access_token  # noqa: E402
from lib.models.user import User, UserRole  # noqa: E402

EXPECTED_TOOL_NAMES = {
    "list_workflow_types",
    "create_project",
    "run_workflow",
    "get_project",
    "list_projects",
    "export_project_docx",
}


@pytest_asyncio.fixture
async def mcp_client():
    async with Client(transport=mcp) as client:
        yield client


@pytest_asyncio.fixture
async def authed_mcp_client():
    """MCP client with a fake auth token and a mock user, for tools that require auth."""
    fake_token = AccessToken(
        token="fake-test-token",
        client_id="test-client",
        scopes=[],
        claims={"email": "test@example.com", "name": "Test User"},
    )
    mock_user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        role=UserRole.USER,
        created_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow(),
        show_experimental_features=False,
    )
    token_reset = _task_access_token.set(fake_token)
    try:
        with patch("lib.api.mcp._resolve_user", AsyncMock(return_value=mock_user)):
            async with Client(transport=mcp) as client:
                yield client
    finally:
        _task_access_token.reset(token_reset)


# --- Tool Registration ---


@pytest.mark.asyncio
async def test_lists_all_expected_tools(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == EXPECTED_TOOL_NAMES


@pytest.mark.asyncio
async def test_each_tool_has_description(mcp_client: Client):
    tools = await mcp_client.list_tools()
    for tool in tools:
        assert tool.description, f"Tool '{tool.name}' missing description"


# --- Tool Annotations ---


@pytest.mark.asyncio
async def test_list_workflow_types_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "list_workflow_types")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_create_project_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "create_project")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.idempotentHint is False
    assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_run_workflow_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "run_workflow")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.openWorldHint is True


@pytest.mark.asyncio
async def test_get_project_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "get_project")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_list_projects_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "list_projects")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_export_project_docx_annotations(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "export_project_docx")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_export_project_docx_schema_has_optional_params(mcp_client: Client):
    tools = await mcp_client.list_tools()
    tool = next(t for t in tools if t.name == "export_project_docx")
    props = tool.inputSchema.get("properties", {})
    assert "project_id" in props
    assert "workflow_types" in props
    assert "severities" in props
    required = tool.inputSchema.get("required", [])
    assert "project_id" in required
    assert "workflow_types" not in required
    assert "severities" not in required


# --- list_workflow_types via Client ---


@pytest.mark.asyncio
async def test_list_workflow_types_returns_workflow_types_and_categories(authed_mcp_client: Client):
    result = await authed_mcp_client.call_tool("list_workflow_types", {})
    text = result.content[0].text
    data = json.loads(text)
    assert "workflow_types" in data
    assert "categories" in data
    assert isinstance(data["workflow_types"], list)
    assert isinstance(data["categories"], list)
    assert len(data["workflow_types"]) > 0
    assert len(data["categories"]) > 0


@pytest.mark.asyncio
async def test_list_workflow_types_entry_has_expected_fields(authed_mcp_client: Client):
    result = await authed_mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    expected_workflow_keys = {
        "type",
        "name",
        "description",
        "needs_web_search",
        "is_experimental",
        "is_internal",
        "is_qa_screener",
        "category",
    }

    for workflow in data["workflow_types"]:
        assert set(workflow.keys()) == expected_workflow_keys


@pytest.mark.asyncio
async def test_list_workflow_types_category_entry_has_expected_fields(authed_mcp_client: Client):
    result = await authed_mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    expected_category_keys = {"slug", "label", "workflows"}

    for category in data["categories"]:
        assert set(category.keys()) == expected_category_keys
        assert isinstance(category["workflows"], list)


@pytest.mark.asyncio
async def test_list_workflow_types_entries_have_valid_types(authed_mcp_client: Client):
    from lib.workflows.models import WorkflowRunType

    result = await authed_mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    valid_types = {t.value for t in WorkflowRunType}
    for workflow in data["workflow_types"]:
        assert workflow["type"] in valid_types, (
            f"Unknown workflow type: {workflow['type']}"
        )


@pytest.mark.asyncio
async def test_list_workflow_types_category_workflows_are_valid_types(authed_mcp_client: Client):
    from lib.workflows.models import WorkflowRunType

    result = await authed_mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    valid_types = {t.value for t in WorkflowRunType}
    for category in data["categories"]:
        for wf_type in category["workflows"]:
            assert wf_type in valid_types, (
                f"Unknown workflow type '{wf_type}' in category '{category['slug']}'"
            )
