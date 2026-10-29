"""Integration tests for the Word add-in chat's threads and suggestions, on real Postgres.

Each test uses fresh Entra object ids, so they never meet another test's rows, and
deletes what those ids own afterwards. What is pinned: a thread is found under every
URL form Word reports and only for its owner, clearing starts afresh, and the chat's
suggestions are handoffs that the Teams list never shows and the agent hears about.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.conversation import Conversation
from lib.models.microsoft_word_chat_thread import MicrosoftWordChatThread
from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.word import chat_suggestions, chat_threads, handoffs
from lib.services.microsoft.word.handoffs import (
    Account,
    HandoffComment,
    HandoffItems,
    ItemResult,
    Requester,
)

GUID = "546f3fae-d9fb-457f-a563-d25549eb3601"
PATH_URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"
ITEMS = HandoffItems(
    comments=[HandoffComment(quote="is the only option", comment="Overclaims.")]
)


@pytest_asyncio.fixture
async def accounts() -> AsyncIterator[tuple[Account, Account]]:
    ana = Account(oid=f"oid-{uuid.uuid4()}", tid="tid-contoso")
    bo = Account(oid=f"oid-{uuid.uuid4()}", tid="tid-contoso")
    yield ana, bo
    oids = [ana.oid, bo.oid]
    async with get_async_db_session() as session:
        await session.execute(
            delete(MicrosoftWordHandoff).where(
                col(MicrosoftWordHandoff.requested_by_oid).in_(oids)
            )
        )
        # The shared rows: each takes its thread with it, where deleting the thread
        # would leave its conversation behind.
        threads = select(col(MicrosoftWordChatThread.id)).where(
            col(MicrosoftWordChatThread.owner_oid).in_(oids)
        )
        await session.execute(
            delete(Conversation).where(col(Conversation.id).in_(threads))
        )
        await session.commit()


async def suggest(account: Account, thread_id: uuid.UUID) -> uuid.UUID:
    return await handoffs.create(
        requester=Requester(oid=account.oid, tid=account.tid, upn="ana@contoso.com"),
        document_name="Draft.docx",
        document_url=PATH_URL,
        keys=chat_threads.thread_keys(PATH_URL),
        items=ITEMS,
        chat_thread_id=thread_id,
    )


@pytest.mark.asyncio
async def test_a_thread_is_resumed_under_the_same_document_and_owner_only(
    accounts: tuple[Account, Account],
) -> None:
    ana, bo = accounts
    started = await chat_threads.current_or_new(ana, PATH_URL)

    again = await chat_threads.current_or_new(ana, PATH_URL)
    for_bo = await chat_threads.current(bo, PATH_URL)
    elsewhere = await chat_threads.current(ana, PATH_URL.replace("Draft", "Other"))

    assert again.id == started.id
    assert for_bo is None
    assert elsewhere is None


@pytest.mark.asyncio
async def test_clearing_sets_a_thread_aside_for_good(
    accounts: tuple[Account, Account],
) -> None:
    ana, bo = accounts
    first = await chat_threads.current_or_new(ana, PATH_URL)

    assert await chat_threads.clear(bo, PATH_URL) is False, "not Bo's to clear"
    assert await chat_threads.clear(ana, PATH_URL) is True
    assert await chat_threads.current(ana, PATH_URL) is None
    second = await chat_threads.current_or_new(ana, PATH_URL)

    assert second.id != first.id


@pytest.mark.asyncio
async def test_a_turn_stamps_when_it_began(
    accounts: tuple[Account, Account],
) -> None:
    ana, _ = accounts
    thread = await chat_threads.current_or_new(ana, PATH_URL)

    await chat_threads.begin_turn(thread.id)
    stamped = await chat_threads.current(ana, PATH_URL)

    assert stamped is not None and stamped.last_turn_at > thread.last_turn_at


@pytest.mark.asyncio
async def test_the_chats_suggestions_live_in_the_chat_not_in_the_teams_list(
    accounts: tuple[Account, Account],
) -> None:
    ana, bo = accounts
    thread = await chat_threads.current_or_new(ana, PATH_URL)
    suggestion_id = await suggest(ana, thread.id)

    from_teams = await handoffs.pending_for(ana)
    mine = await chat_suggestions.suggestion_for(suggestion_id, ana)
    theirs = await chat_suggestions.suggestion_for(suggestion_id, bo)

    assert suggestion_id not in {row.id for row in from_teams}
    assert mine is not None and mine.status == "pending"
    assert theirs is None


@pytest.mark.asyncio
async def test_applying_one_is_stored_and_heard_on_the_next_turn(
    accounts: tuple[Account, Account],
) -> None:
    ana, _ = accounts
    thread = await chat_threads.current_or_new(ana, PATH_URL)
    suggestion_id = await suggest(ana, thread.id)
    assert await handoffs.start(suggestion_id, ana)

    reported = await handoffs.report_applied(
        suggestion_id, ana, [ItemResult(index=0, applied=True)]
    )
    settled = await chat_suggestions.for_thread(thread.id)
    news = chat_suggestions.news(settled)
    await chat_suggestions.mark_heard([s.id for s in chat_suggestions.unheard(settled)])
    told_again = chat_suggestions.news(await chat_suggestions.for_thread(thread.id))

    assert reported is True
    assert settled[0].status == "applied"
    assert settled[0].outcome is not None and settled[0].outcome.applied == 1
    assert "1 of 1" in news
    assert told_again == ""


@pytest.mark.asyncio
async def test_a_card_grows_only_while_it_is_pending_and_only_for_its_owner(
    accounts: tuple[Account, Account],
) -> None:
    ana, bo = accounts
    thread = await chat_threads.current_or_new(ana, PATH_URL)
    card = await suggest(ana, thread.id)
    more = HandoffItems(
        comments=[*ITEMS.comments, HandoffComment(quote="the base case", comment="?")]
    )

    assert await chat_suggestions.replace_items(card, bo, more) is False
    assert await chat_suggestions.replace_items(card, ana, more) is True
    grown = await chat_suggestions.suggestion_for(card, ana)
    assert grown is not None and len(grown.items.comments) == 2

    assert await handoffs.start(card, ana)
    assert await chat_suggestions.replace_items(card, ana, ITEMS) is False
    applying = await chat_suggestions.suggestion_for(card, ana)
    assert applying is not None and len(applying.items.comments) == 2


@pytest.mark.asyncio
async def test_two_first_messages_at_once_start_one_thread(
    accounts: tuple[Account, Account],
) -> None:
    ana, _ = accounts

    first, second = await asyncio.gather(
        chat_threads.current_or_new(ana, PATH_URL),
        chat_threads.current_or_new(ana, PATH_URL),
    )

    assert first.id == second.id


@pytest.mark.asyncio
async def test_one_turn_at_a_time_and_a_dead_ones_claim_runs_out(
    accounts: tuple[Account, Account],
) -> None:
    ana, _ = accounts
    thread = await chat_threads.current_or_new(ana, PATH_URL)

    token = await chat_threads.claim(thread.id)
    assert token is not None
    assert await chat_threads.claim(thread.id) is None
    await chat_threads.release(thread.id, token)
    assert await chat_threads.claim(thread.id) is not None

    # A worker that died mid-turn never releases: its claim runs out.
    async with get_async_db_session() as session:
        await session.execute(
            update(MicrosoftWordChatThread)
            .where(col(MicrosoftWordChatThread.id) == thread.id)
            .values(
                running_since=datetime.now(UTC)
                - chat_threads.STALE_CLAIM
                - timedelta(minutes=1)
            )
        )
        await session.commit()
    taken = await chat_threads.claim(thread.id)
    assert taken is not None

    # The stalled turn coming back must not let go of the claim that replaced its own.
    await chat_threads.release(thread.id, token)
    assert await chat_threads.claim(thread.id) is None
