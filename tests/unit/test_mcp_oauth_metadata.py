"""OAuth discovery documents served for the MCP endpoint (RFC 9728 + RFC 8414).

Covers the path a client walks from an unauthenticated request to the
authorization server:

- #775: strict clients (Claude Desktop) reject authorization-server metadata
  unless ``issuer`` is identical to the advertised identifier (RFC 8414 §3.3).
- #774: MCP SDK clients (Claude Code, Claude Desktop) reject a protected
  resource that does not match the URL they were configured with, so ``/mcp``
  and ``/mcp/`` must both pass.
"""

import re
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProvider
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from lib.api.mcp_auth import create_mcp_auth
from lib.api.mcp_middlewares import MCPTrailingSlashMiddleware

ORIGIN = "https://app.example.com"
BASE_URL = f"{ORIGIN}/mcp"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _config(provider: str, cimd: bool) -> MagicMock:
    mock_config = MagicMock()
    mock_config.AUTH_GOOGLE_ID = "google-id" if provider == "google" else None
    mock_config.AUTH_GOOGLE_SECRET = "google-secret" if provider == "google" else None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = "entra-id" if provider == "entra" else None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = "entra-secret" if provider == "entra" else None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = (
        "https://login.microsoftonline.com/tenant-abc/v2.0" if provider == "entra" else None
    )
    mock_config.MCP_BASE_URL = BASE_URL
    mock_config.MCP_CIMD_ENABLED = cimd
    mock_config.AUTH_SECRET = "test-auth-secret-for-kdf"
    return mock_config


def _client(auth: OAuthProvider) -> TestClient:
    """Wire the provider the way ``lib.api.main`` does: discovery at the root, MCP under /mcp."""
    mcp_app = FastMCP("test", auth=auth).http_app(path="/", stateless_http=True)
    app = Starlette(
        routes=[
            *auth.get_well_known_routes(mcp_path="/"),
            Mount("/mcp", app=mcp_app),
        ]
    )
    return TestClient(MCPTrailingSlashMiddleware(app), base_url=ORIGIN)


def _resource_metadata_path(response_headers: dict[str, str]) -> str:
    match = re.search(r'resource_metadata="([^"]+)"', response_headers["www-authenticate"])
    assert match, response_headers["www-authenticate"]
    return urlparse(match.group(1)).path


def _discovery_path(issuer: str) -> str:
    """RFC 8414 §3.1: insert the well-known segment between host and issuer path."""
    issuer_path = urlparse(issuer).path.rstrip("/")
    return f"/.well-known/oauth-authorization-server{issuer_path}"


def _sdk_accepts_resource(server_url: str, resource: str) -> bool:
    """The MCP SDK's ``checkResourceAllowed``, which Claude Code and Desktop run."""
    requested, configured = urlparse(server_url), urlparse(resource)
    if (requested.scheme, requested.netloc) != (configured.scheme, configured.netloc):
        return False
    if len(requested.path) < len(configured.path):
        return False
    return (requested.path.rstrip("/") + "/").startswith(configured.path.rstrip("/") + "/")


@pytest.fixture(params=["google", "entra"])
def provider_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=[False, True], ids=["dcr", "cimd"])
def client(provider_name: str, request: pytest.FixtureRequest) -> TestClient:
    with patch("lib.api.mcp_auth.config", _config(provider_name, cimd=request.param)):
        auth = create_mcp_auth()
    assert isinstance(auth, OAuthProvider)
    return _client(auth)


@pytest.mark.parametrize("server_url", [BASE_URL, f"{BASE_URL}/"], ids=["no-slash", "slash"])
def test_client_can_follow_the_challenge_to_the_authorization_server(
    client: TestClient, server_url: str
) -> None:
    challenge = client.post(urlparse(server_url).path, json=INITIALIZE, headers=MCP_HEADERS)
    assert challenge.status_code == 401

    resource = client.get(_resource_metadata_path(dict(challenge.headers))).json()
    assert _sdk_accepts_resource(server_url, resource["resource"])

    authorization_server = resource["authorization_servers"][0]
    metadata = client.get(_discovery_path(authorization_server))
    assert metadata.status_code == 200
    assert metadata.json()["issuer"] == authorization_server


def test_resource_is_advertised_without_trailing_slash(client: TestClient) -> None:
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()

    assert resource["resource"] == BASE_URL


def test_resource_metadata_also_served_at_slash_path(client: TestClient) -> None:
    slashless = client.get("/.well-known/oauth-protected-resource/mcp")
    slash = client.get("/.well-known/oauth-protected-resource/mcp/")

    assert slash.status_code == 200
    assert slash.json() == slashless.json()


def test_endpoints_stay_under_the_mcp_mount(client: TestClient) -> None:
    metadata = client.get("/.well-known/oauth-authorization-server").json()

    assert metadata["authorization_endpoint"] == f"{BASE_URL}/authorize"
    assert metadata["token_endpoint"] == f"{BASE_URL}/token"
    assert metadata["registration_endpoint"] == f"{BASE_URL}/register"


def test_mounted_copy_reports_the_same_issuer(client: TestClient) -> None:
    root = client.get("/.well-known/oauth-authorization-server").json()
    mounted = client.get("/mcp/.well-known/oauth-authorization-server").json()

    assert mounted == root


def test_cors_preflight_still_answered(client: TestClient) -> None:
    response = client.options(
        "/.well-known/oauth-authorization-server",
        headers={"Origin": "https://claude.ai", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
