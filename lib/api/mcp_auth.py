import json
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from key_value.aio.protocols.key_value import AsyncKeyValue
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from pydantic import AnyHttpUrl
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from lib.api.mcp_discovery import slashless_resource_url, with_slash_resource_metadata
from lib.config.env import config
from lib.mcp.postgres_kv_store import PostgresKeyValueStore

logger = logging.getLogger(__name__)

_WELL_KNOWN_AUTH_PATH = "/.well-known/oauth-authorization-server"


class _FixIssuerMiddleware:
    """ASGI wrapper that overwrites the 'issuer' field in the auth-server metadata.

    fastmcp 3.2+ passes base_url (e.g. .../mcp) as the issuer to create_auth_routes
    even when issuer_url is set to the origin root.  That makes the issuer in the
    well-known document inconsistent with the authorization_servers entry in the
    protected-resource document, breaking RFC 8414 §3.3 (Claude Desktop rejects
    the flow).  This wrapper patches the response body to restore the correct issuer.
    """

    def __init__(self, app: ASGIApp, issuer: str) -> None:
        self._app = app
        self._issuer = issuer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        chunks: list[bytes] = []
        start: dict[str, Any] = {}

        async def intercept(event: Any) -> None:
            if event["type"] == "http.response.start":
                start.update(event)
            elif event["type"] == "http.response.body":
                chunks.append(event.get("body", b""))
                if not event.get("more_body", False):
                    body = b"".join(chunks)
                    try:
                        data = json.loads(body)
                        data["issuer"] = self._issuer
                        body = json.dumps(data).encode()
                    except Exception:
                        pass
                    headers = [
                        (k, v) for k, v in start.get("headers", [])
                        if k.lower() != b"content-length"
                    ] + [(b"content-length", str(len(body)).encode())]
                    await send({**start, "headers": headers})
                    await send({"type": "http.response.body", "body": body, "more_body": False})

        await self._app(scope, receive, intercept)


def _with_fixed_issuer(routes: list[Route], issuer: str) -> list[Route]:
    """Wrap the auth-server well-known endpoint to report the correct issuer URL."""
    return [
        Route(
            route.path,
            endpoint=_FixIssuerMiddleware(route.endpoint, issuer),
            methods=route.methods,
            name=route.name,
            include_in_schema=route.include_in_schema,
        )
        if route.path == _WELL_KNOWN_AUTH_PATH
        else route
        for route in routes
    ]

# Stable salt: rotating it would invalidate every stored OAuth registration
# and force every client through re-auth. Versioned so we can rotate
# deliberately if AUTH_SECRET is ever compromised.
_MCP_STORAGE_SALT = "mcp-oauth-storage-v1"


# Both providers advertise the MCP resource as ``…/mcp`` so clients configured
# with either ``…/mcp`` or ``…/mcp/`` accept it (issue #774, see
# lib.api.mcp_discovery). FastMCP reads the resource URL through
# ``_get_resource_url`` everywhere (protected-resource document,
# WWW-Authenticate challenge, token audience), so that is the hook.


class SlashTolerantGoogleProvider(GoogleProvider):
    """Google provider that accepts MCP clients configured with or without the trailing slash."""

    def _get_resource_url(self, path: str | None = None) -> AnyHttpUrl | None:
        return slashless_resource_url(super()._get_resource_url(path))

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = _with_fixed_issuer(
            with_slash_resource_metadata(super().get_routes(mcp_path)),
            str(self.issuer_url),
        )
        return routes


class SlashTolerantAzureProvider(AzureProvider):
    """Entra ID provider that accepts MCP clients configured with or without the trailing slash."""

    def _get_resource_url(self, path: str | None = None) -> AnyHttpUrl | None:
        return slashless_resource_url(super()._get_resource_url(path))

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = _with_fixed_issuer(
            with_slash_resource_metadata(super().get_routes(mcp_path)),
            str(self.issuer_url),
        )
        return routes


def _root_url(url: str) -> str:
    """Strip path from a URL, returning just scheme + netloc."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _build_client_storage() -> AsyncKeyValue:
    """Build the shared OAuth ``client_storage`` for MCP providers.

    Without this, FastMCP defaults to an in-memory store, which loses client
    registrations and PKCE state across pods — the root cause of the
    re-auth hang on multi-pod deployments (RANDZ-534).

    Encryption key is derived from ``AUTH_SECRET`` via PBKDF2 (handled by
    ``FernetEncryptionWrapper``) so we don't need a second secret in the
    environment.
    """
    return FernetEncryptionWrapper(
        key_value=PostgresKeyValueStore(),
        source_material=config.AUTH_SECRET,
        salt=_MCP_STORAGE_SALT,
    )


def create_mcp_auth():
    """Build the FastMCP auth provider based on available OAuth env vars.

    Google takes priority when both providers are configured (mirrors
    the frontend provider ordering in auth.ts).

    Raises RuntimeError if neither Google nor Entra ID credentials are set.
    """
    base_url = config.MCP_BASE_URL

    # issuer_url at root so auth-server discovery lives at
    # /.well-known/oauth-authorization-server (no path suffix).
    # Some MCP clients (e.g. Claude) don't support path-aware discovery.
    # FastMCP 4 reports this as the metadata ``issuer`` too, which strict
    # clients such as Claude Desktop require (RFC 8414 §3.3, issue #775).
    issuer_url = _root_url(base_url)

    client_storage = _build_client_storage()

    if config.AUTH_GOOGLE_ID and config.AUTH_GOOGLE_SECRET:
        logger.info("MCP auth: using Google OAuth provider")
        return SlashTolerantGoogleProvider(
            client_id=config.AUTH_GOOGLE_ID,
            client_secret=config.AUTH_GOOGLE_SECRET,
            base_url=base_url,
            issuer_url=issuer_url,
            required_scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            enable_cimd=config.MCP_CIMD_ENABLED,
            client_storage=client_storage,
        )

    if (
        config.AUTH_MICROSOFT_ENTRA_ID_ID
        and config.AUTH_MICROSOFT_ENTRA_ID_SECRET
        and config.AUTH_MICROSOFT_ENTRA_ID_ISSUER
    ):
        # Extract tenant_id from issuer URL
        # Format: https://login.microsoftonline.com/{tenant_id}/v2.0
        tenant_id = config.AUTH_MICROSOFT_ENTRA_ID_ISSUER.rstrip("/").split("/")[-2]

        logger.info("MCP auth: using Microsoft Entra ID OAuth provider")
        return SlashTolerantAzureProvider(
            client_id=config.AUTH_MICROSOFT_ENTRA_ID_ID,
            client_secret=config.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            tenant_id=tenant_id,
            base_url=base_url,
            issuer_url=issuer_url,
            required_scopes=["mcp-access"],
            enable_cimd=config.MCP_CIMD_ENABLED,
            client_storage=client_storage,
        )

    raise RuntimeError(
        "MCP auth requires either Google (AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET) "
        "or Entra ID (AUTH_MICROSOFT_ENTRA_ID_ID, AUTH_MICROSOFT_ENTRA_ID_SECRET, "
        "AUTH_MICROSOFT_ENTRA_ID_ISSUER) environment variables to be set."
    )
