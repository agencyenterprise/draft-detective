"""Tests for the add-in chat's threads.

A thread is found by the document whatever URL form Word reports, and only for the
account that owns it.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.microsoft_word_chat_thread import MicrosoftWordChatThread
from lib.services.microsoft.word import chat_threads, handoffs
from lib.services.microsoft.word.handoffs import Account

ANA = Account(oid="oid-ana", tid="tid-contoso")
GUID = "546f3fae-d9fb-457f-a563-d25549eb3601"
PATH_URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"
VIEWER_URL = (
    "https://contoso.sharepoint.com/sites/Policy/_layouts/15/Doc.aspx"
    f"?sourcedoc=%7B{GUID.upper()}%7D&file=Draft.docx"
)
NOW = datetime.now(UTC)


def thread(keys: list[str], last_turn: datetime = NOW) -> MicrosoftWordChatThread:
    return MicrosoftWordChatThread(
        id=uuid.uuid4(),
        owner_oid=ANA.oid,
        owner_tid=ANA.tid,
        document_name="Draft.docx",
        document_url=PATH_URL,
        document_keys=keys,
        created_at=last_turn,
        last_turn_at=last_turn,
    )


def session_listing(rows: list[Any]) -> Any:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


class TestRecognisingTheDocument:
    def test_a_saved_document_is_known_by_its_path(self) -> None:
        assert chat_threads.thread_keys(PATH_URL) == sorted(
            handoffs.keys_for_url(PATH_URL)
        )

    def test_a_local_file_is_known_by_its_path(self) -> None:
        # Word desktop reports a file that is not in the cloud by its path on disk.
        assert chat_threads.thread_keys("/Users/Ana/Draft.docx") == [
            "url:/users/ana/draft.docx"
        ]

    def test_an_unsaved_document_has_one_shared_key(self) -> None:
        assert chat_threads.thread_keys("  ") == [chat_threads.UNSAVED]

    def test_each_unsaved_pane_has_its_own_key(self) -> None:
        first = chat_threads.thread_keys("unsaved:1b2c")
        second = chat_threads.thread_keys("unsaved:9f8e")

        assert first != second and chat_threads.UNSAVED not in first
        assert chat_threads.document_name("unsaved:1b2c") == "this document"

    def test_the_name_comes_from_the_url(self) -> None:
        assert chat_threads.document_name(PATH_URL) == "Draft.docx"
        assert chat_threads.document_name("") == "this document"

    def test_a_doc_aspx_link_is_named_by_its_file_not_its_page(self) -> None:
        url = (
            "https://contoso-my.sharepoint.com/:w:/r/personal/ana/_layouts/15/Doc.aspx"
            "?sourcedoc=%7B97126C1E%7D&file=v3%20CERN%20for%20AI.docx&action=default"
        )
        assert chat_threads.document_name(url) == "v3 CERN for AI.docx"


class TestFindingTheCurrentThread:
    @pytest.mark.asyncio
    async def test_it_is_found_under_any_url_form_word_reports(self) -> None:
        mine = thread([f"guid:{GUID}", *chat_threads.thread_keys(PATH_URL)])
        other = thread(["guid:00000000-0000-0000-0000-000000000000"])
        session = session_listing([other, mine])
        with patch.object(chat_threads, "get_async_db_session", return_value=session):
            found = await chat_threads.current(ANA, VIEWER_URL)

        assert found is mine
        sql = str(session.execute.await_args.args[0]).lower()
        assert "owner_oid" in sql and "owner_tid" in sql and "cleared_at is null" in sql

    @pytest.mark.asyncio
    async def test_none_when_no_thread_is_about_this_document(self) -> None:
        session = session_listing([thread(["guid:other"])])
        with patch.object(chat_threads, "get_async_db_session", return_value=session):
            assert await chat_threads.current(ANA, PATH_URL) is None
