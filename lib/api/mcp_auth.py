import logging
from urllib.parse import urlparse, urlunparse

from lib.config.env import config

logger = logging.getLogger(__name__)


def _root_url(url: str) -> str:
    """Strip path from a URL, returning just scheme + netloc."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


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
    issuer_url = _root_url(base_url)

    if config.AUTH_GOOGLE_ID and config.AUTH_GOOGLE_SECRET:
        from fastmcp.server.auth.providers.google import GoogleProvider

        logger.info("MCP auth: using Google OAuth provider")
        return GoogleProvider(
            client_id=config.AUTH_GOOGLE_ID,
            client_secret=config.AUTH_GOOGLE_SECRET,
            base_url=base_url,
            issuer_url=issuer_url,
            required_scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
        )

    if (
        config.AUTH_MICROSOFT_ENTRA_ID_ID
        and config.AUTH_MICROSOFT_ENTRA_ID_SECRET
        and config.AUTH_MICROSOFT_ENTRA_ID_ISSUER
    ):
        from fastmcp.server.auth.providers.azure import AzureProvider

        # Extract tenant_id from issuer URL
        # Format: https://login.microsoftonline.com/{tenant_id}/v2.0
        tenant_id = config.AUTH_MICROSOFT_ENTRA_ID_ISSUER.rstrip("/").split("/")[-2]

        logger.info("MCP auth: using Microsoft Entra ID OAuth provider")
        return AzureProvider(
            client_id=config.AUTH_MICROSOFT_ENTRA_ID_ID,
            client_secret=config.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            tenant_id=tenant_id,
            base_url=base_url,
            issuer_url=issuer_url,
            required_scopes=["mcp-access"],
        )

    raise RuntimeError(
        "MCP auth requires either Google (AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET) "
        "or Entra ID (AUTH_MICROSOFT_ENTRA_ID_ID, AUTH_MICROSOFT_ENTRA_ID_SECRET, "
        "AUTH_MICROSOFT_ENTRA_ID_ISSUER) environment variables to be set."
    )
