"""Turn an unhandled exception into a JSON 500 that CORS can still decorate.

Starlette answers an uncaught exception from ServerErrorMiddleware, which always
wraps every middleware added with `add_middleware`, CORSMiddleware included. That
500 leaves without Access-Control-Allow-Origin, so the browser reports a network
error ("Failed to fetch") instead of the status. Registered inside CORS, this
middleware answers first, and the 500 passes back out through CORS.
"""

import logging

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class ServerErrorJSONMiddleware:
    """Log an unhandled exception and answer `{"detail": "Internal server error"}` (500).

    Once the response has started (a stream that fails midway), a second response
    can't be sent: the exception propagates to the server as before.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            if response_started:
                raise
            logger.exception(
                "Unhandled error on %s %s", scope.get("method"), scope.get("path")
            )
            response = JSONResponse(
                {"detail": "Internal server error"}, status_code=500
            )
            await response(scope, receive, send)
