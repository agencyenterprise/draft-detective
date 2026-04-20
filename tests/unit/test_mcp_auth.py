"""Unit tests for MCP auth provider creation."""

from unittest.mock import ANY, MagicMock, patch

import pytest

from lib.api.mcp_auth import _root_url, create_mcp_auth


def _base_mock_config() -> MagicMock:
    """Shared baseline: no creds, real AUTH_SECRET for storage key derivation.

    Tests that need creds override them. ``AUTH_SECRET`` is a real string so
    ``FernetEncryptionWrapper``'s PBKDF2 derivation succeeds (it rejects
    ``MagicMock`` / empty values).
    """
    mock_config = MagicMock()
    mock_config.AUTH_GOOGLE_ID = None
    mock_config.AUTH_GOOGLE_SECRET = None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = None
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = None
    mock_config.MCP_BASE_URL = "http://localhost:8000/mcp"
    mock_config.MCP_CIMD_ENABLED = False
    mock_config.AUTH_SECRET = "test-auth-secret-for-kdf"
    return mock_config


# --- _root_url ---


def test_root_url_strips_path():
    assert _root_url("https://example.com/mcp/v1") == "https://example.com"


def test_root_url_preserves_port():
    assert _root_url("http://localhost:8000/mcp") == "http://localhost:8000"


def test_root_url_handles_root_url():
    assert _root_url("https://example.com") == "https://example.com"


# --- create_mcp_auth ---


def test_create_mcp_auth_raises_without_credentials():
    mock_config = _base_mock_config()

    with patch("lib.api.mcp_auth.config", mock_config):
        with pytest.raises(RuntimeError, match="MCP auth requires either Google"):
            create_mcp_auth()


def test_create_mcp_auth_with_google_credentials():
    mock_config = _base_mock_config()
    mock_config.AUTH_GOOGLE_ID = "google-client-id"
    mock_config.AUTH_GOOGLE_SECRET = "google-client-secret"
    mock_config.MCP_BASE_URL = "https://api.example.com/mcp"

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.google.GoogleProvider"
        ) as MockProvider,
    ):
        create_mcp_auth()

    MockProvider.assert_called_once_with(
        client_id="google-client-id",
        client_secret="google-client-secret",
        base_url="https://api.example.com/mcp",
        issuer_url="https://api.example.com",
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        enable_cimd=False,
        client_storage=ANY,
    )


def test_create_mcp_auth_with_entra_id_credentials():
    mock_config = _base_mock_config()
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = "entra-id"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = "entra-secret"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = (
        "https://login.microsoftonline.com/tenant-abc/v2.0"
    )
    mock_config.MCP_BASE_URL = "https://api.example.com/mcp"

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.azure.AzureProvider"
        ) as MockProvider,
    ):
        create_mcp_auth()

    MockProvider.assert_called_once_with(
        client_id="entra-id",
        client_secret="entra-secret",
        tenant_id="tenant-abc",
        base_url="https://api.example.com/mcp",
        issuer_url="https://api.example.com",
        required_scopes=["mcp-access"],
        enable_cimd=False,
        client_storage=ANY,
    )


def test_create_mcp_auth_google_takes_priority():
    """When both Google and Entra ID are configured, Google is selected."""
    mock_config = _base_mock_config()
    mock_config.AUTH_GOOGLE_ID = "google-id"
    mock_config.AUTH_GOOGLE_SECRET = "google-secret"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = "entra-id"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = "entra-secret"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = (
        "https://login.microsoftonline.com/tenant/v2.0"
    )

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.google.GoogleProvider"
        ) as MockGoogle,
        patch(
            "fastmcp.server.auth.providers.azure.AzureProvider"
        ) as MockAzure,
    ):
        create_mcp_auth()

    MockGoogle.assert_called_once()
    MockAzure.assert_not_called()


def test_create_mcp_auth_extracts_tenant_from_issuer():
    """Tenant ID is correctly parsed from the Microsoft issuer URL."""
    mock_config = _base_mock_config()
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = "id"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = "secret"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = (
        "https://login.microsoftonline.com/my-tenant-123/v2.0"
    )
    mock_config.MCP_BASE_URL = "http://localhost/mcp"

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.azure.AzureProvider"
        ) as MockProvider,
    ):
        create_mcp_auth()

    call_kwargs = MockProvider.call_args.kwargs
    assert call_kwargs["tenant_id"] == "my-tenant-123"


def test_create_mcp_auth_cimd_enabled_google():
    """CIMD flag is forwarded to Google provider when enabled."""
    mock_config = _base_mock_config()
    mock_config.AUTH_GOOGLE_ID = "google-client-id"
    mock_config.AUTH_GOOGLE_SECRET = "google-client-secret"
    mock_config.MCP_BASE_URL = "https://api.example.com/mcp"
    mock_config.MCP_CIMD_ENABLED = True

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.google.GoogleProvider"
        ) as MockProvider,
    ):
        create_mcp_auth()

    call_kwargs = MockProvider.call_args.kwargs
    assert call_kwargs["enable_cimd"] is True
    assert "client_storage" in call_kwargs


def test_create_mcp_auth_cimd_enabled_entra_id():
    """CIMD flag is forwarded to Azure provider when enabled."""
    mock_config = _base_mock_config()
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ID = "entra-id"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_SECRET = "entra-secret"
    mock_config.AUTH_MICROSOFT_ENTRA_ID_ISSUER = (
        "https://login.microsoftonline.com/tenant-abc/v2.0"
    )
    mock_config.MCP_BASE_URL = "https://api.example.com/mcp"
    mock_config.MCP_CIMD_ENABLED = True

    with (
        patch("lib.api.mcp_auth.config", mock_config),
        patch(
            "fastmcp.server.auth.providers.azure.AzureProvider"
        ) as MockProvider,
    ):
        create_mcp_auth()

    call_kwargs = MockProvider.call_args.kwargs
    assert call_kwargs["enable_cimd"] is True
    assert "client_storage" in call_kwargs


def test_client_storage_wraps_postgres_in_fernet_derived_from_auth_secret():
    """Storage is a FernetEncryptionWrapper over Postgres, keyed off AUTH_SECRET."""
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

    from lib.api.mcp_auth import _build_client_storage
    from lib.mcp.postgres_kv_store import PostgresKeyValueStore

    mock_config = _base_mock_config()

    with patch("lib.api.mcp_auth.config", mock_config):
        storage = _build_client_storage()

    assert isinstance(storage, FernetEncryptionWrapper)
    assert isinstance(storage.key_value, PostgresKeyValueStore)
