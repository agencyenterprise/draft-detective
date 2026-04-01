"""Tests for MCP server tool registration and list_workflow_types using FastMCP Client.

Follows the testing best practices from https://gofastmcp.com/servers/testing,
using pytest-asyncio fixtures with the FastMCP Client for in-memory testing.
"""

import json

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

EXPECTED_TOOL_NAMES = {
    "list_workflow_types",
    "create_project",
    "run_workflow",
    "get_project",
}


@pytest_asyncio.fixture
async def mcp_client():
    async with Client(transport=mcp) as client:
        yield client


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


# --- list_workflow_types via Client ---


@pytest.mark.asyncio
async def test_list_workflow_types_returns_workflows(mcp_client: Client):
    result = await mcp_client.call_tool("list_workflow_types", {})
    text = result.content[0].text
    data = json.loads(text)
    assert "workflows" in data
    assert isinstance(data["workflows"], list)
    assert len(data["workflows"]) > 0


@pytest.mark.asyncio
async def test_list_workflow_types_entry_has_expected_fields(mcp_client: Client):
    result = await mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    expected_keys = {
        "type",
        "name",
        "description",
        "order",
        "is_experimental",
        "requires_human_trigger",
        "required_dependencies",
        "optional_dependencies",
    }

    for workflow in data["workflows"]:
        assert set(workflow.keys()) == expected_keys


@pytest.mark.asyncio
async def test_list_workflow_types_sorted_by_order(mcp_client: Client):
    result = await mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    orders = [w["order"] for w in data["workflows"]]
    assert orders == sorted(orders)


@pytest.mark.asyncio
async def test_list_workflow_types_entries_have_valid_types(mcp_client: Client):
    from lib.workflows.models import WorkflowRunType

    result = await mcp_client.call_tool("list_workflow_types", {})
    data = json.loads(result.content[0].text)

    valid_types = {t.value for t in WorkflowRunType}
    for workflow in data["workflows"]:
        assert workflow["type"] in valid_types, (
            f"Unknown workflow type: {workflow['type']}"
        )
