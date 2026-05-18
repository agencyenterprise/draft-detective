from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastmcp.server.auth import AccessToken

from lib.config.env import config as env_config
from lib.models.user import User
from lib.services.users import get_or_create_user_by_email


def _looks_like_email(value: str) -> bool:
    """Minimal check: contains exactly one '@' with text on both sides."""
    parts = value.split("@")
    return len(parts) == 2 and all(parts)


async def resolve_user(token: AccessToken) -> User:
    """Resolve the DB user from an authenticated OAuth access token."""
    claims = token.claims
    upstream = claims.get("upstream_claims", {})
    # Azure Entra ID: email is optional and preferred_username (UPN) may be
    # the only identifier.  FastMCP validates the upstream Azure JWT and
    # exposes its claims at the top level, but also embeds them under
    # "upstream_claims" in its own reference JWT — check both paths.
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or upstream.get("email")
        or upstream.get("preferred_username")
    )
    name = claims.get("name") or upstream.get("name") or email
    if not email:
        raise RuntimeError("Token missing 'email' claim")
    if not _looks_like_email(email):
        raise RuntimeError(f"Resolved identity '{email}' is not a valid email address")
    return await get_or_create_user_by_email(email=email, name=name)


def build_project_url(project_id: str) -> str:
    base = env_config.FRONTEND_URL.rstrip("/")
    return f"{base}/projects/{project_id}"


def build_settings_url() -> str:
    return f"{env_config.FRONTEND_URL.rstrip('/')}/account"


def build_tus_url() -> str:
    """Derive the TUS endpoint URL from MCP_BASE_URL by stripping the /mcp suffix."""
    base = env_config.MCP_BASE_URL
    if base.endswith("/mcp"):
        base = base[: -len("/mcp")]
    return base.rstrip("/") + "/tus"


def require_api_key(user: User) -> None:
    """Raise a clear error when no OpenAI API key is available."""
    if user.encrypted_openai_api_key or env_config.OPENAI_API_KEY:
        return
    settings_url = build_settings_url()
    raise ValueError(
        f"Your account ({user.email}) does not have an OpenAI API key configured on Draft Detective. "
        "This is a one-time setup: open the link below, sign in with the same account, "
        "and save your key. It will be encrypted and tied to your account only. "
        f"Once saved, all future MCP requests will pick it up automatically.\n\n"
        f"Settings page: {settings_url}"
    )


def mint_tus_bearer_token(user: User) -> tuple[str, int]:
    """Mint a short-lived JWT for TUS uploads. Returns (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    expires_in_seconds = 900
    payload = {
        "email": user.email,
        "name": user.name,
        "iss": "ai-reviewer",
        "aud": "ai-reviewer-api",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return (
        pyjwt.encode(payload, env_config.AUTH_SECRET, algorithm="HS512"),
        expires_in_seconds,
    )
