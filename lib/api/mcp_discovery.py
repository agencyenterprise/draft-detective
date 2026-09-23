"""Protected-resource URL fix for the MCP endpoint (issue #774).

Our MCP endpoint is the root of the /mcp mount, so FastMCP names the resource
``…/mcp/``. MCP SDK clients (Claude Code, Claude Desktop) only accept a resource
whose path is a prefix of the URL they were configured with, so ``…/mcp/``
rejects clients configured with ``…/mcp``; ``…/mcp`` accepts both.
"""

from pydantic import AnyHttpUrl
from starlette.routing import Route

PROTECTED_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def slashless_resource_url(url: AnyHttpUrl | None) -> AnyHttpUrl | None:
    """Drop the trailing slash from a resource URL that has a path (``…/mcp/`` → ``…/mcp``)."""
    if url is None or not url.path or url.path == "/":
        return url
    return AnyHttpUrl(str(url).rstrip("/"))


def with_slash_resource_metadata(routes: list[Route]) -> list[Route]:
    """Also serve the protected-resource document at the path clients derive from ``…/mcp/``."""
    fixed: list[Route] = []
    for route in routes:
        fixed.append(route)
        if route.path.startswith(PROTECTED_RESOURCE_METADATA_PATH) and not route.path.endswith("/"):
            fixed.append(
                Route(
                    f"{route.path}/",
                    endpoint=route.app,
                    methods=route.methods,
                    name=route.name,
                    include_in_schema=route.include_in_schema,
                )
            )
    return fixed
