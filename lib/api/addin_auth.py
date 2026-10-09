"""Who is calling from the Word add-in: a Microsoft account, identified by its object id.

The add-in's routes act on behalf of one Microsoft account. That account is what a
handoff from Teams is released to, so it has to be the same identity Teams knows -- the
Entra object id (``oid``) in its tenant (``tid``) -- not an email address, which can
differ between a UPN and a mailbox and is not unique across sign-in providers.

Two kinds of bearer token carry it:

- **An Entra token from Office single sign-on.** The pane asks Office for a token for
  the user already signed in to Word, issued for the app Draft Detective's own
  "Sign in with Microsoft" uses. It is verified against Microsoft's published signing
  keys, and must be for that app, carry the ``access_as_user`` scope and come from the
  tenant it names -- and, when that app's issuer names one tenant, from that tenant.

  It is accepted only where Microsoft sign-in is configured: all three of
  ``AUTH_MICROSOFT_ENTRA_ID_ID``, ``_SECRET`` and ``_ISSUER``. A deployment that does not
  sign its users in with Microsoft has no add-in sign-in either.
- **A Draft Detective session token** from the dialog the pane falls back to when single
  sign-on is unavailable. Only one from a Microsoft sign-in counts, since only that one
  carries the object id.
"""

import asyncio
import logging
import re
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

from lib.api.auth import ALGORITHM, SECRET_KEY
from lib.config.env import config

logger = logging.getLogger(__name__)

# The same keys sign tokens for every tenant; which tenant issued one is checked below.
ENTRA_KEYS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
ADDIN_SCOPE = "access_as_user"
MICROSOFT_PROVIDER = "microsoft-entra-id"

_entra_keys = PyJWKClient(ENTRA_KEYS_URL, cache_keys=True, lifespan=3600)
_bearer = HTTPBearer()


class AddinIdentity(BaseModel):
    """A Microsoft account, as the add-in's routes know it."""

    oid: str
    tid: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


_TENANT_ISSUER = re.compile(
    r"^https://login\.microsoftonline\.com/[0-9a-f-]{36}/v2\.0/?$", re.IGNORECASE
)


def addin_app() -> tuple[Optional[str], Optional[str]]:
    """The client id Office tokens must be issued for, and the one issuer to require.

    The app Draft Detective signs users in with, and nothing unless all three of its
    settings are present. A tenant-specific ``AUTH_MICROSOFT_ENTRA_ID_ISSUER`` means only
    that tenant's tokens are accepted; a ``common`` or ``organizations`` one leaves each
    token to be checked against the tenant it names.
    """

    client_id = config.AUTH_MICROSOFT_ENTRA_ID_ID
    issuer = (config.AUTH_MICROSOFT_ENTRA_ID_ISSUER or "").strip()
    if not (client_id and config.AUTH_MICROSOFT_ENTRA_ID_SECRET and issuer):
        return None, None
    required = issuer.rstrip("/") if _TENANT_ISSUER.match(issuer) else None
    return client_id, required


def from_entra_token(token: str) -> Optional[AddinIdentity]:
    """The identity in an Office single sign-on token, or None if it is not one we accept.

    Blocking: the first call for a signing key fetches Microsoft's key set.
    """

    client_id, required_issuer = addin_app()
    if not client_id:
        return None
    try:
        key = _entra_keys.get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            options={"require": ["exp", "iss", "aud", "oid", "tid"]},
        )
    except jwt.PyJWTError as error:
        logger.info("rejected an add-in Entra token: %s", error)
        return None

    if claims["iss"] != f"https://login.microsoftonline.com/{claims['tid']}/v2.0":
        logger.info("rejected an add-in Entra token from issuer %s", claims["iss"])
        return None
    if required_issuer and claims["iss"].lower() != required_issuer.lower():
        logger.info("rejected an add-in Entra token from another tenant: %s", claims["iss"])
        return None
    if ADDIN_SCOPE not in str(claims.get("scp", "")).split():
        logger.info("rejected an add-in Entra token without the %s scope", ADDIN_SCOPE)
        return None

    return AddinIdentity(
        oid=str(claims["oid"]),
        tid=str(claims["tid"]),
        email=claims.get("email") or claims.get("preferred_username"),
        name=claims.get("name"),
    )


def from_session_token(token: str) -> Optional[AddinIdentity]:
    """The identity in a Draft Detective session token from a Microsoft sign-in."""

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer="ai-reviewer",
            audience="ai-reviewer-api",
        )
    except jwt.PyJWTError as error:
        logger.info("rejected an add-in session token: %s", error)
        return None

    if claims.get("provider") != MICROSOFT_PROVIDER:
        logger.info("rejected an add-in session token from %s", claims.get("provider"))
        return None
    if not claims.get("oid"):
        logger.info("rejected an add-in session token without an object id")
        return None
    return AddinIdentity(
        oid=str(claims["oid"]),
        tid=claims.get("tid"),
        email=claims.get("email"),
        name=claims.get("name"),
    )


async def identify(token: str) -> Optional[AddinIdentity]:
    """Whichever of the two tokens this is, or None."""

    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError:
        return None
    if algorithm == "RS256":
        return await asyncio.to_thread(from_entra_token, token)
    return from_session_token(token)


def _kind(token: str) -> str:
    algorithm = jwt.get_unverified_header(token).get("alg")
    return "single sign-on" if algorithm == "RS256" else "dialog session"


async def get_addin_identity(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AddinIdentity:
    """The Microsoft account calling, or 401."""

    identity = await identify(credentials.credentials)
    if identity is not None:
        logger.info("add-in call as %s (%s)", identity.oid, _kind(credentials.credentials))
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with a Microsoft account",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity
