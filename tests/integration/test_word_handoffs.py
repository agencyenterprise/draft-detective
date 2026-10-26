"""Integration tests for handoffs from Teams, on real Postgres.

What is pinned: a handoff is released only to the account that asked for it (its
object id, and its tenant when both sides know one), each step happens once however
often the add-in repeats it, so Teams hears about an Apply once, and a handoff past its
week is gone: skipped by every read, and deleted whenever one is stored or listed.

Each test uses fresh Entra object ids and deletes what they own afterwards.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.word import handoffs
from lib.services.microsoft.word.handoffs import (
    Account,
    HandoffComment,
    HandoffEdit,
    HandoffItems,
    InvalidResults,
    ItemResult,
    Requester,
)

URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"
ITEMS = HandoffItems(
    comments=[HandoffComment(quote="is the only option", comment="Overclaims.")],
    edits=[HandoffEdit(quote="recieve", replacement="receive")],
)
REFERENCE = {
    "serviceUrl": "https://smba.trafficmanager.net/amer/",
    "channelId": "msteams",
    "conversation": {"id": "19:thread@thread.v2"},
}


@pytest_asyncio.fixture
async def ana() -> AsyncIterator[Account]:
    account = Account(oid=f"oid-{uuid.uuid4()}", tid="tid-contoso")
    yield account
    async with get_async_db_session() as session:
        await session.execute(
            delete(MicrosoftWordHandoff).where(
                col(MicrosoftWordHandoff.requested_by_oid) == account.oid
            )
        )
        await session.commit()


async def ask(account: Account, tid: str | None = "tid-contoso") -> uuid.UUID:
    """A handoff from Teams, as the bot stores one."""

    return await handoffs.create(
        requester=Requester(oid=account.oid, tid=tid, upn="ana@contoso.com"),
        document_name="Draft.docx",
        document_url=URL,
        keys=sorted(handoffs.keys_for_url(URL)),
        items=ITEMS,
        reference=REFERENCE,
    )


async def listed(account: Account) -> dict[uuid.UUID, str]:
    return {row.id: row.status for row in await handoffs.pending_for(account)}


async def age(handoff_id: uuid.UUID, by: timedelta) -> None:
    """Move a handoff's creation back by ``by``."""

    async with get_async_db_session() as session:
        await session.execute(
            update(MicrosoftWordHandoff)
            .where(col(MicrosoftWordHandoff.id) == handoff_id)
            .values(created_at=datetime.now(UTC) - by)
        )
        await session.commit()


async def stored(handoff_id: uuid.UUID) -> MicrosoftWordHandoff | None:
    async with get_async_db_session() as session:
        return (
            await session.execute(
                select(MicrosoftWordHandoff).where(
                    col(MicrosoftWordHandoff.id) == handoff_id
                )
            )
        ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_only_the_account_that_asked_can_see_or_close_it(ana: Account) -> None:
    handoff_id = await ask(ana)
    someone_else = Account(oid=f"oid-{uuid.uuid4()}", tid=ana.tid)
    same_id_other_tenant = Account(oid=ana.oid, tid="tid-fabrikam")

    for stranger in (someone_else, same_id_other_tenant):
        assert handoff_id not in await listed(stranger)
        assert await handoffs.start(handoff_id, stranger) is False
        assert await handoffs.finish(handoff_id, stranger, "dismissed") is None

    assert await listed(ana) == {handoff_id: "pending"}


@pytest.mark.asyncio
async def test_a_handoff_is_stored_under_whoever_asked(ana: Account) -> None:
    row = await stored(await ask(ana))

    assert row is not None
    assert (row.requested_by_oid, row.requested_by_tid, row.requested_by_upn) == (
        ana.oid,
        ana.tid,
        "ana@contoso.com",
    )
    assert row.status == "pending" and row.chat_thread_id is None


@pytest.mark.asyncio
async def test_the_newest_handoff_is_listed_first(ana: Account) -> None:
    older = await ask(ana)
    await age(older, timedelta(hours=1))
    newer = await ask(ana)

    assert [row.id for row in await handoffs.pending_for(ana)] == [newer, older]


@pytest.mark.asyncio
async def test_a_tenant_is_compared_only_when_both_sides_know_it(
    ana: Account,
) -> None:
    without_tenant = await ask(ana, tid=None)
    with_tenant = await ask(ana)

    # Stored without a tenant: the object id alone has to match.
    assert set(await listed(ana)) == {without_tenant, with_tenant}
    # Signed in without a tenant: the object id alone is compared.
    assert set(await listed(Account(oid=ana.oid))) == {without_tenant, with_tenant}


@pytest.mark.asyncio
async def test_an_apply_is_claimed_once_and_reported_to_teams_once(
    ana: Account,
) -> None:
    handoff_id = await ask(ana)
    results = [
        ItemResult(index=0, applied=True),
        ItemResult(index=1, applied=False, reason="not_found"),
    ]

    assert await handoffs.start(handoff_id, ana) is True
    assert await handoffs.start(handoff_id, ana) is False
    # Started but not reported: still shown, so an interrupted Apply is not lost.
    assert await listed(ana) == {handoff_id: "applying"}

    with patch.object(handoffs.bot, "post_later", AsyncMock()) as post:
        assert await handoffs.report_applied(handoff_id, ana, results) is True
        assert await handoffs.report_applied(handoff_id, ana, results) is False
        assert await handoffs.finish(handoff_id, ana, "dismissed") is None

    post.assert_awaited_once()
    assert post.await_args is not None
    reference, text = post.await_args.args
    assert reference.conversation.id == "19:thread@thread.v2"
    assert "1 of 2" in text
    row = await stored(handoff_id)
    assert row is not None and row.status == "applied"
    assert row.outcome is not None and row.finished_at is not None
    assert [item["applied"] for item in row.outcome["items"]] == [True, False]
    assert handoff_id not in await listed(ana)


@pytest.mark.asyncio
async def test_results_it_does_not_have_leave_the_apply_open(ana: Account) -> None:
    handoff_id = await ask(ana)
    assert await handoffs.start(handoff_id, ana)

    with patch.object(handoffs.bot, "post_later", AsyncMock()) as post:
        with pytest.raises(InvalidResults):
            await handoffs.report_applied(
                handoff_id, ana, [ItemResult(index=2, applied=True)]
            )

    post.assert_not_awaited()
    assert await listed(ana) == {handoff_id: "applying"}


@pytest.mark.asyncio
async def test_a_dismissed_handoff_is_closed_without_an_outcome(ana: Account) -> None:
    handoff_id = await ask(ana)

    finished = await handoffs.finish(handoff_id, ana, "dismissed")

    assert finished is not None and finished.items == ITEMS
    assert finished.document_name == "Draft.docx"
    assert await handoffs.start(handoff_id, ana) is False
    row = await stored(handoff_id)
    assert row is not None and row.status == "dismissed" and row.outcome is None
    assert await listed(ana) == {}


@pytest.mark.asyncio
async def test_a_handoff_past_its_week_is_unusable_and_swept(ana: Account) -> None:
    handoff_id = await ask(ana)
    await age(handoff_id, handoffs.KEPT_FOR + timedelta(days=1))

    assert await handoffs.start(handoff_id, ana) is False
    assert await handoffs.finish(handoff_id, ana, "dismissed") is None
    # Skipped even when the sweep has not removed it yet.
    with patch.object(handoffs, "_sweep", AsyncMock()):
        assert await listed(ana) == {}

    assert await listed(ana) == {}
    assert await stored(handoff_id) is None


@pytest.mark.asyncio
async def test_storing_a_handoff_sweeps_anyones_past_their_week(ana: Account) -> None:
    # Someone else's, so the fixture leaves it to the sweep. Under xdist another test's
    # create may sweep it first: that can hide a break here, never fail it.
    expired = await ask(Account(oid=f"oid-{uuid.uuid4()}"))
    await age(expired, handoffs.KEPT_FOR + timedelta(days=1))

    await ask(ana)

    assert await stored(expired) is None
