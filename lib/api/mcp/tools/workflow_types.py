from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.services.workflow_types import get_all_workflow_types


@mcp.tool(
    annotations=ToolAnnotations(
        destructive_hint=False,
        idempotent_hint=True,
        read_only_hint=True,
        open_world_hint=False,
    )
)
async def list_workflow_types(token: AccessToken = CurrentAccessToken()) -> str:
    """
    Lists all available workflow / analysis types that can be run on a project / document,
    along with the ordered category display config.

    workflow_types: flat list of all workflows with type identifier (used when starting a
    workflow), display name, description, and dependency information.
    categories: ordered list of categories, each with an ordered list of workflow type slugs
    that belong to it — use this to understand grouping and display order.
    """
    # The listing is the same for every caller, but resolving the user still
    # validates the token's identity claims (and provisions the account on a
    # first call), which is the behaviour every other tool relies on.
    await helpers.resolve_user(token)
    return get_all_workflow_types().model_dump_json()
