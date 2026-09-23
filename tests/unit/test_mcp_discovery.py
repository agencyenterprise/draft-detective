"""Unit tests for the protected-resource URL helpers in lib.api.mcp_discovery."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from lib.api.mcp_discovery import slashless_resource_url, with_slash_resource_metadata

PRM_PATH = "/.well-known/oauth-protected-resource/mcp"


async def _metadata(request: Request) -> Response:
    return JSONResponse({"resource": "https://app.example.com/mcp"})


@pytest.mark.parametrize(
    "endpoint",
    [_metadata, CORSMiddleware(Starlette(routes=[Route("/{p:path}", _metadata)]), allow_origins=["*"])],
    ids=["function", "asgi-app"],
)
def test_slash_alias_serves_the_same_document(endpoint: Callable[..., Any]) -> None:
    routes = with_slash_resource_metadata([Route(PRM_PATH, endpoint=endpoint, methods=["GET"])])
    client = TestClient(Starlette(routes=routes))

    slashless = client.get(PRM_PATH)
    slash = client.get(f"{PRM_PATH}/")

    assert slash.status_code == 200
    assert slash.json() == slashless.json()


def test_other_routes_are_left_alone() -> None:
    route = Route("/authorize", endpoint=_metadata)

    assert with_slash_resource_metadata([route]) == [route]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://app.example.com/mcp/", "https://app.example.com/mcp"),
        ("https://app.example.com/mcp", "https://app.example.com/mcp"),
        ("https://app.example.com/", "https://app.example.com/"),
    ],
)
def test_slashless_resource_url(url: str, expected: str) -> None:
    assert str(slashless_resource_url(AnyHttpUrl(url))) == expected


def test_slashless_resource_url_passes_none_through() -> None:
    assert slashless_resource_url(None) is None
