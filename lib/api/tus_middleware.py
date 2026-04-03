from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


class TusTerminationMiddleware(BaseHTTPMiddleware):
    """Handle TUS termination 404s gracefully - treat as already deleted."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # TUS DELETE on completed uploads returns 404 - treat as success
        if (
            request.method == "DELETE"
            and request.url.path.startswith("/tus/")
            and response.status_code == 404
        ):
            return Response(status_code=204)
        return response
