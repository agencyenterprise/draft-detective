"""An unhandled exception still reaches the browser as a 500 it can read.

Starlette builds the 500 for an uncaught exception in ServerErrorMiddleware,
which sits outside every middleware added with `add_middleware`, CORS included.
Without a handler inside CORS, that 500 leaves without Access-Control-Allow-Origin
and the browser reports a network error instead of the status.
"""

import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from lib.api.cors import add_cors_middleware
from lib.api.server_error_middleware import ServerErrorJSONMiddleware

ORIGIN = "http://localhost:3000"
PATH = "/api/__test_unhandled_error"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A route that raises, behind the API's CORS setup (not `lib.api.main`, whose import reads config)."""
    app = FastAPI()
    add_cors_middleware(app)

    @app.get(PATH)
    async def boom() -> None:
        raise RuntimeError("boom from a route")

    yield TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_is_a_500_the_browser_can_read(client: TestClient) -> None:
    response = client.get(PATH, headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_unhandled_error_is_logged_with_its_traceback(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        client.get(PATH, headers={"Origin": ORIGIN})

    logged = [
        r
        for r in caplog.records
        if r.exc_info and "boom from a route" in str(r.exc_info[1])
    ]
    assert logged, "the exception and its traceback should be logged"


@pytest.mark.asyncio
async def test_error_after_the_response_started_is_reraised() -> None:
    """A stream that fails midway can't be replaced by a 500: the error propagates."""
    sent: list[Message] = []

    async def streaming_app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {"type": "http.response.body", "body": b"data: 1\n\n", "more_body": True}
        )
        raise RuntimeError("stream broke")

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = ServerErrorJSONMiddleware(streaming_app)
    with pytest.raises(RuntimeError, match="stream broke"):
        await middleware({"type": "http", "method": "GET", "path": "/"}, receive, send)

    assert [m["type"] for m in sent] == ["http.response.start", "http.response.body"]
