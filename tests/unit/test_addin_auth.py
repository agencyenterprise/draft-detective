"""Tests for who the Word add-in is calling as.

Everything the add-in can see -- above all handoffs, which carry document text -- is
released by the Microsoft account these return, so what is pinned is mostly refusal:
a token for another app, from another tenant than it claims, without the add-in's
scope, expired, or a Draft Detective session that did not come from a Microsoft
sign-in, must all come back as nobody.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from lib.api import addin_auth
from lib.api.auth import ALGORITHM, SECRET_KEY

CLIENT_ID = "e7ca390f-cdd6-4f6a-bd7f-2a4bb66e31d6"
TENANT = "51fd520c-7591-436c-b066-c9bac44ea8e0"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def entra_token(**overrides: Any) -> str:
    """An Office single sign-on token as Entra would issue it, signed with ``KEY``."""

    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "aud": CLIENT_ID,
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "tid": TENANT,
        "oid": "oid-ana",
        "scp": "access_as_user",
        "preferred_username": "ana@contoso.com",
        "name": "Ana",
        "iat": now,
        "exp": now + timedelta(hours=1),
        **overrides,
    }
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})


def session_token(**overrides: Any) -> str:
    """A Draft Detective session token, as the frontend mints it."""

    claims: dict[str, Any] = {
        "sub": "microsoft-entra-id:abc",
        "email": "ana@contoso.com",
        "name": "Ana",
        "provider": "microsoft-entra-id",
        "oid": "oid-ana",
        "tid": TENANT,
        "iss": "ai-reviewer",
        "aud": "ai-reviewer-api",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        **overrides,
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def entra(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Microsoft's key set, answered locally with our test key's public half."""

    # Microsoft sign-in configured, as the add-in requires: all three settings.
    monkeypatch.setattr(addin_auth.config, "AUTH_MICROSOFT_ENTRA_ID_ID", CLIENT_ID)
    monkeypatch.setattr(addin_auth.config, "AUTH_MICROSOFT_ENTRA_ID_SECRET", "a-secret")
    monkeypatch.setattr(
        addin_auth.config,
        "AUTH_MICROSOFT_ENTRA_ID_ISSUER",
        f"https://login.microsoftonline.com/{TENANT}/v2.0",
    )
    signing_key = MagicMock(key=KEY.public_key())
    with patch.object(
        addin_auth._entra_keys, "get_signing_key_from_jwt", return_value=signing_key
    ) as keys:
        yield keys


class TestOfficeSingleSignOn:
    @pytest.mark.asyncio
    async def test_a_token_for_the_add_in_names_the_account(self) -> None:
        identity = await addin_auth.identify(entra_token())

        assert identity is not None
        assert (identity.oid, identity.tid) == ("oid-ana", TENANT)
        assert identity.email == "ana@contoso.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "overrides",
        [
            {"aud": "another-app"},
            {"iss": "https://login.microsoftonline.com/another-tenant/v2.0"},
            {"scp": "User.Read"},
            {"exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            {"oid": None},
        ],
        ids=["another app", "issuer not its tenant", "no add-in scope", "expired", "no object id"],
    )
    async def test_anything_else_is_nobody(self, overrides: dict[str, Any]) -> None:
        claims = {key: value for key, value in overrides.items() if value is not None}
        token = entra_token(**claims)
        if overrides.get("oid", "") is None:
            payload = jwt.decode(token, options={"verify_signature": False})
            payload.pop("oid")
            token = jwt.encode(payload, KEY, algorithm="RS256", headers={"kid": "k1"})

        assert await addin_auth.identify(token) is None

    @pytest.mark.asyncio
    async def test_a_token_signed_by_someone_else_is_nobody(self) -> None:
        stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            jwt.decode(entra_token(), options={"verify_signature": False}),
            stranger,
            algorithm="RS256",
            headers={"kid": "k1"},
        )

        assert await addin_auth.identify(token) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "unset",
        ["AUTH_MICROSOFT_ENTRA_ID_ID", "AUTH_MICROSOFT_ENTRA_ID_SECRET", "AUTH_MICROSOFT_ENTRA_ID_ISSUER"],
    )
    async def test_without_microsoft_sign_in_configured_none_is_accepted(
        self, unset: str, monkeypatch: pytest.MonkeyPatch, entra: Any
    ) -> None:
        """A deployment that does not sign users in with Microsoft has no add-in sign-in."""

        monkeypatch.setattr(addin_auth.config, unset, None)

        assert await addin_auth.identify(entra_token()) is None
        entra.assert_not_called()


class TestTheSignInAppsTenant:
    """The issuer of the app Draft Detective signs in with decides which tenants get in."""

    OTHER_TENANT = "00000000-0000-0000-0000-00000000beef"

    def other_tenant_token(self) -> str:
        return entra_token(
            tid=self.OTHER_TENANT,
            iss=f"https://login.microsoftonline.com/{self.OTHER_TENANT}/v2.0",
        )

    @pytest.mark.asyncio
    async def test_a_tenant_specific_issuer_keeps_other_tenants_out(self) -> None:
        assert await addin_auth.identify(self.other_tenant_token()) is None

    @pytest.mark.asyncio
    async def test_a_multi_tenant_issuer_lets_any_tenant_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            addin_auth.config,
            "AUTH_MICROSOFT_ENTRA_ID_ISSUER",
            "https://login.microsoftonline.com/common/v2.0",
        )

        assert await addin_auth.identify(self.other_tenant_token()) is not None


class TestTheDialogFallback:
    @pytest.mark.asyncio
    async def test_a_microsoft_sign_in_names_the_account(self) -> None:
        identity = await addin_auth.identify(session_token())

        assert identity is not None
        assert (identity.oid, identity.tid) == ("oid-ana", TENANT)

    @pytest.mark.asyncio
    async def test_a_google_sign_in_is_nobody_even_with_the_same_email(self) -> None:
        assert await addin_auth.identify(session_token(provider="google", oid=None)) is None

    @pytest.mark.asyncio
    async def test_a_session_from_before_the_object_id_was_carried_is_nobody(self) -> None:
        assert await addin_auth.identify(session_token(oid=None)) is None

    @pytest.mark.asyncio
    async def test_a_session_signed_with_another_secret_is_nobody(self) -> None:
        forged = jwt.encode(
            jwt.decode(session_token(), options={"verify_signature": False}),
            "not-the-secret",
            algorithm=ALGORITHM,
        )

        assert await addin_auth.identify(forged) is None


class TestTheDependency:
    @pytest.mark.asyncio
    async def test_nobody_is_a_401(self) -> None:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not a token")

        with pytest.raises(HTTPException) as raised:
            await addin_auth.get_addin_identity(credentials)

        assert raised.value.status_code == 401

    @pytest.mark.asyncio
    async def test_somebody_is_returned(self) -> None:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=entra_token())

        identity = await addin_auth.get_addin_identity(credentials)

        assert identity.oid == "oid-ana"
