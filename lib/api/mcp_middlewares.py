from starlette.types import ASGIApp, Receive, Scope, Send


class MCPTrailingSlashMiddleware:
    """Accept /mcp without trailing slash so clients that don't follow 307 redirects still work."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/mcp":
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)
