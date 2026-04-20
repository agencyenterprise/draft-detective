import logging
from urllib.parse import urlparse, urlunparse

from key_value.aio.protocols.key_value import AsyncKeyValue
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from lib.config.env import config
from lib.mcp.postgres_kv_store import PostgresKeyValueStore

logger = logging.getLogger(__name__)

# Stable salt: rotating it would invalidate every stored OAuth registration
# and force every client through re-auth. Versioned so we can rotate
# deliberately if AUTH_SECRET is ever compromised.
_MCP_STORAGE_SALT = "mcp-oauth-storage-v1"


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
    issuer_url = _root_url(base_url)

    client_storage = _build_client_storage()

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
            enable_cimd=config.MCP_CIMD_ENABLED,
            client_storage=client_storage,
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
            enable_cimd=config.MCP_CIMD_ENABLED,
            client_storage=client_storage,
        )

    raise RuntimeError(
        "MCP auth requires either Google (AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET) "
        "or Entra ID (AUTH_MICROSOFT_ENTRA_ID_ID, AUTH_MICROSOFT_ENTRA_ID_SECRET, "
        "AUTH_MICROSOFT_ENTRA_ID_ISSUER) environment variables to be set."
    )
