from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.services.workflow_types import get_workflow_types_for_user


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
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
    user = await helpers.resolve_user(token)
    return get_workflow_types_for_user(user).model_dump_json()
