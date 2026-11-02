"""Which Draft Detective user a Microsoft account is, matched by email for listing.

An email links an account only when it can be trusted to mean that user: the email
claim itself, from the one tenant Draft Detective's Microsoft sign-in accepts.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lib.services.microsoft import linked_users

TENANT = "51fd520c-7591-436c-b066-c9bac44ea8e0"
ONE_TENANT = f"https://login.microsoftonline.com/{TENANT}/v2.0"
USER = SimpleNamespace(id=uuid.uuid4())


def configured(issuer: str | None):
    return patch.object(linked_users.config, "AUTH_MICROSOFT_ENTRA_ID_ISSUER", issuer)


def upserting():
    return patch.object(
        linked_users, "get_or_create_user_by_email", AsyncMock(return_value=USER)
    )


@pytest.mark.asyncio
async def test_an_account_of_the_configured_tenant_is_its_emails_user() -> None:
    with configured(ONE_TENANT), upserting() as upsert:
        found = await linked_users.user_for("ana@contoso.com", "Ana", TENANT.upper())

    assert found == USER.id
    upsert.assert_awaited_once_with(email="ana@contoso.com", name="Ana")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("issuer", "email", "tenant"),
    [
        (ONE_TENANT, None, TENANT),
        (ONE_TENANT, "ana@contoso.com", str(uuid.uuid4())),
        (ONE_TENANT, "ana@contoso.com", None),
        ("https://login.microsoftonline.com/common/v2.0", "ana@contoso.com", TENANT),
        (None, "ana@contoso.com", TENANT),
    ],
    ids=[
        "no email claim",
        "another tenant",
        "tenant unknown",
        "multi-tenant sign-in",
        "no Microsoft sign-in",
    ],
)
async def test_an_email_that_cannot_be_trusted_links_nobody(
    issuer: str | None, email: str | None, tenant: str | None
) -> None:
    with configured(issuer), upserting() as upsert:
        assert await linked_users.user_for(email, "Ana", tenant) is None

    upsert.assert_not_awaited()
