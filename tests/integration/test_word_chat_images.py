"""Integration tests for conversations and the images of a document read in one.

Every conversation, on any surface, has a row in ``conversations``; images of a document
read in the Word add-in's chat or in Teams are ``files`` rows owned by it instead of a
project. What is pinned, on real Postgres: every file has exactly one owner, a Word
chat's images are kept for the copies of its document it holds, a Teams
conversation's accumulate per document read,
both go with their conversation, a Teams conversation is started once however many
questions race to start it, and the download route, which serves a file only through
its project, never serves a conversation's.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.conversation import Conversation, ConversationKind
from lib.models.file import File, FileRole
from lib.models.microsoft_teams_conversation import MicrosoftTeamsConversation
from lib.models.microsoft_word_chat_thread import MicrosoftWordChatThread
from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.models.user import User
from lib.services import conversations
from lib.services.files.image_extraction import ExtractedImage
from lib.services.files.images import (
    add_conversation_images,
    prune_conversation_images,
)
from lib.services.files.service import check_file_access
from lib.services.microsoft.word import chat_threads, handoffs
from lib.services.microsoft.word.handoffs import (
    Account,
    HandoffComment,
    HandoffItems,
    Requester,
)
from lib.services.users import get_or_create_user_by_email

URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"


async def remove(conversation_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        await conversations.remove(session, conversation_id)
        await session.commit()


@pytest_asyncio.fixture
async def word_chat() -> AsyncIterator[uuid.UUID]:
    account = Account(oid=f"oid-{uuid.uuid4()}", tid="tid-contoso")
    thread = await chat_threads.current_or_new(account, URL)
    yield thread.id
    await remove(thread.id)


def image(tmp_path: Path, name: str) -> ExtractedImage:
    path = tmp_path / f"{name}.png"
    path.write_bytes(name.encode())
    return ExtractedImage(
        image_path=str(path),
        mime_type="image/png",
        file_size=len(name),
        content_hash=f"{name}-{uuid.uuid4()}",
    )


async def owned_by(conversation_id: uuid.UUID) -> list[File]:
    async with get_async_db_session() as session:
        rows = await session.execute(
            select(File).where(col(File.conversation_id) == conversation_id)
        )
        return list(rows.scalars())


@pytest.mark.asyncio
async def test_a_word_chat_is_a_conversation_under_its_own_id(
    word_chat: uuid.UUID,
) -> None:
    async with get_async_db_session() as session:
        shared = await session.get(Conversation, word_chat)

    assert shared is not None and shared.kind == ConversationKind.WORD


@pytest.mark.asyncio
async def test_a_word_chats_images_accumulate_and_go_with_the_conversation(
    word_chat: uuid.UUID, tmp_path: Path
) -> None:
    first = image(tmp_path, "first")
    await add_conversation_images(word_chat, [first])
    second = image(tmp_path, "second")
    await add_conversation_images(word_chat, [second])

    # The earlier copy's images stay: markdown already stored may still name them.
    rows = await owned_by(word_chat)
    assert {row.id for row in rows} == {first.id, second.id}
    assert all(row.project_id is None for row in rows)

    # Once a newer copy is stored, the images no copy names go; the others stay.
    third = image(tmp_path, "third")
    await prune_conversation_images(word_chat, keep={second.id})
    await add_conversation_images(word_chat, [third])
    assert {row.id for row in await owned_by(word_chat)} == {second.id, third.id}

    await remove(word_chat)
    assert await owned_by(word_chat) == []
    async with get_async_db_session() as session:
        assert await session.get(MicrosoftWordChatThread, word_chat) is None


@pytest.mark.asyncio
async def test_a_figure_changed_and_changed_back_keeps_its_file(
    word_chat: uuid.UUID, tmp_path: Path
) -> None:
    # Content-addressed: the figure restored is the first copy's file again.
    a_first, b = image(tmp_path, "a"), image(tmp_path, "b")
    await add_conversation_images(word_chat, [a_first])
    await add_conversation_images(word_chat, [b])
    await prune_conversation_images(word_chat, keep={a_first.id, b.id})
    a_again = a_first.model_copy(update={"id": uuid.uuid4()})

    # As the route does it: the new copy's rows first, then everything else but the
    # stored copy's (B) and the new copy's (A again).
    await add_conversation_images(word_chat, [a_again])
    await prune_conversation_images(word_chat, keep={b.id, a_again.id})

    assert {row.id for row in await owned_by(word_chat)} == {b.id, a_again.id}
    assert Path(a_again.image_path).exists()


@pytest.mark.asyncio
async def test_a_teams_conversation_is_started_once_and_keeps_every_documents_images(
    tmp_path: Path,
) -> None:
    teams_id = f"19:test-{uuid.uuid4()}@thread.tacv2;messageid=1"
    # Two questions in a new conversation, at once.
    started = await asyncio.gather(
        conversations.for_teams(teams_id), conversations.for_teams(teams_id)
    )
    conversation_id = started[0]
    try:
        assert started[1] == conversation_id
        assert await conversations.for_teams(teams_id) == conversation_id

        # Two documents in one conversation: the second adds, it does not replace.
        first, second = image(tmp_path, "rev1"), image(tmp_path, "rev2")
        await add_conversation_images(conversation_id, [first])
        await add_conversation_images(conversation_id, [second])
        assert {row.id for row in await owned_by(conversation_id)} == {
            first.id,
            second.id,
        }
    finally:
        await remove(conversation_id)

    assert await owned_by(conversation_id) == []
    async with get_async_db_session() as session:
        assert await session.get(MicrosoftTeamsConversation, conversation_id) is None


@pytest.mark.asyncio
async def test_a_file_without_an_owner_is_refused() -> None:
    async with get_async_db_session() as session:
        session.add(
            File(
                id=uuid.uuid4(),
                file_name="orphan.png",
                file_path="/nowhere/orphan.png",
                file_type="image/png",
                file_size=1,
                content_hash="orphan",
                role=FileRole.EXTRACTED_IMAGE,
            )
        )
        with pytest.raises(IntegrityError, match="ck_files_one_owner"):
            await session.commit()


@pytest.mark.asyncio
async def test_the_download_route_never_serves_a_conversations_image(
    word_chat: uuid.UUID, tmp_path: Path
) -> None:
    stored = image(tmp_path, "figure")
    await add_conversation_images(word_chat, [stored])

    with pytest.raises(HTTPException) as refused:
        await check_file_access(stored.id, uuid.uuid4())

    assert refused.value.status_code == 404


@pytest.mark.asyncio
async def test_a_surfaces_row_cannot_exist_without_its_conversation() -> None:
    async with get_async_db_session() as session:
        session.add(
            MicrosoftTeamsConversation(
                id=uuid.uuid4(), teams_conversation_id=f"19:{uuid.uuid4()}"
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest_asyncio.fixture
async def user_id() -> AsyncIterator[uuid.UUID]:
    user = await get_or_create_user_by_email(f"ana-{uuid.uuid4()}@contoso.com", "Ana")
    yield user.id
    async with get_async_db_session() as session:
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


async def listed_under(conversation_id: uuid.UUID) -> uuid.UUID | None:
    async with get_async_db_session() as session:
        shared = await session.get(Conversation, conversation_id)
    assert shared is not None
    return shared.user_id


@pytest.mark.asyncio
async def test_a_new_word_chat_is_listed_under_its_user_and_outlives_them(
    user_id: uuid.UUID,
) -> None:
    account = Account(oid=f"oid-{uuid.uuid4()}", tid="tid-contoso")
    asked = 0

    async def starter() -> uuid.UUID:
        nonlocal asked
        asked += 1
        return user_id

    thread = await chat_threads.current_or_new(account, URL, starter)
    again = await chat_threads.current_or_new(account, URL, starter)
    try:
        assert again.id == thread.id
        # Asked once, when the conversation started; not on every message.
        assert asked == 1
        assert await listed_under(thread.id) == user_id

        # Listing only: deleting the user unlists the conversation, and the account
        # that owns it keeps it.
        async with get_async_db_session() as session:
            await session.execute(delete(User).where(col(User.id) == user_id))
            await session.commit()
        assert await listed_under(thread.id) is None
        async with get_async_db_session() as session:
            assert await session.get(MicrosoftWordChatThread, thread.id) is not None
    finally:
        await remove(thread.id)


@pytest.mark.asyncio
async def test_a_teams_conversation_is_listed_under_whoever_asked_first(
    user_id: uuid.UUID,
) -> None:
    teams_id = f"19:test-{uuid.uuid4()}@thread.tacv2;messageid=1"

    async def first() -> uuid.UUID:
        return user_id

    async def second() -> uuid.UUID:
        raise AssertionError("an existing conversation does not ask again")

    conversation_id = await conversations.for_teams(teams_id, first)
    try:
        assert await conversations.for_teams(teams_id, second) == conversation_id
        assert await listed_under(conversation_id) == user_id
    finally:
        await remove(conversation_id)


@pytest.mark.asyncio
async def test_a_conversations_cards_go_with_it(word_chat: uuid.UUID) -> None:
    card = await handoffs.create(
        requester=Requester(oid="oid-x", tid="tid-contoso", upn="x@contoso.com"),
        document_name="Draft.docx",
        document_url=URL,
        keys=chat_threads.thread_keys(URL),
        items=HandoffItems(comments=[HandoffComment(quote="q", comment="c")]),
        chat_thread_id=word_chat,
    )

    await remove(word_chat)

    async with get_async_db_session() as session:
        assert await session.get(MicrosoftWordHandoff, card) is None
