from lib.api.mcp.instance import mcp, mcp_auth

# Importing the tool modules registers each @mcp.tool with the FastMCP instance.
from lib.api.mcp.tools import (  # noqa: F401
    files,
    projects,
    revisions,
    uploads,
    workflow_types,
    workflows,
)

mcp_app = mcp.http_app(
    path="/",
    stateless_http=True,  # Stateless mode is needed since production runs multiple instances (workers)
)

__all__ = ["mcp", "mcp_app", "mcp_auth"]
