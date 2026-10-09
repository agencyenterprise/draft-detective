"""Tests for handing review work from Teams to the Word add-in.

Two things carry the weight. The add-in recognises a document only by the URL Word
reports, which takes different forms in different clients, so ``keys_for_url`` and
``document_keys`` must meet on at least one key for every form. And a handoff is
released only to the person who asked, once: ``finish`` is a single conditional UPDATE
scoped to their address.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.word import handoffs
from lib.services.microsoft.word.handoffs import (
    FinishedHandoff,
    HandoffComment,
    HandoffEdit,
    HandoffItems,
    HandoffOutcome,
    ItemOutcome,
    Account,
    Requester,
)

GUID = "546F3FAE-D9FB-457F-A563-D25549EB3601"
LIBRARY = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents"

# A drive item as Graph returns it for a Word document in a folder.
ITEM: dict[str, Any] = {
    "name": "Draft v3.docx",
    "eTag": f'"{{{GUID}}},4"',
    "webUrl": (
        "https://contoso.sharepoint.com/sites/Policy/_layouts/15/Doc.aspx"
        f"?sourcedoc=%7B{GUID}%7D&file=Draft%20v3.docx&action=default"
    ),
    "parentReference": {"driveId": "b!x", "path": "/drives/b!x/root:/Reports"},
}


def session_returning(first: Any = None) -> Any:
    result = MagicMock()
    result.first.return_value = first
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def statements(session: Any) -> list[str]:
    return [str(call[0][0]).lower() for call in session.execute.await_args_list]


def stored(keys: list[str]) -> MicrosoftWordHandoff:
    return MicrosoftWordHandoff(
        id=uuid.uuid4(),
        requested_by_oid="oid-ana",
        requested_by_tid="tid-contoso",
        requested_by_upn="ana@contoso.com",
        document_name="Draft v3.docx",
        document_url=ITEM["webUrl"],
        document_keys=keys,
        items={"comments": [{"quote": "the words", "comment": "a point"}], "edits": []},
        reference={},
        status="pending",
        created_at=datetime.now(timezone.utc),
    )


ANA = Account(oid="oid-ana", tid="tid-contoso")


class TestWhoOwnsAHandoff:
    """The condition every lookup and update is scoped by."""

    def sql(self, account: Account) -> str:
        return str(handoffs._owned_by(account).compile(compile_kwargs={"literal_binds": True}))

    def test_the_object_id_must_match(self) -> None:
        assert "requested_by_oid = 'oid-ana'" in self.sql(Account(oid="oid-ana"))

    def test_with_a_tenant_both_must_match(self) -> None:
        sql = self.sql(ANA)
        assert "requested_by_oid = 'oid-ana'" in sql
        assert "requested_by_tid = 'tid-contoso'" in sql
        assert " AND " in sql


class TestRecognisingTheDocument:
    def test_a_viewer_link_is_known_by_its_unique_id(self) -> None:
        assert handoffs.keys_for_url(ITEM["webUrl"]) == {f"guid:{GUID.lower()}"}

    def test_a_path_is_known_by_its_path_whatever_the_encoding(self) -> None:
        encoded = f"{LIBRARY}/Reports/Draft%20v3.docx"
        plain = "https://Contoso.sharepoint.com/sites/Policy/Shared Documents/Reports/Draft v3.docx"

        assert handoffs.keys_for_url(encoded) == handoffs.keys_for_url(plain)
        assert len(handoffs.keys_for_url(plain)) == 1

    def test_a_sharing_link_identifies_nothing(self) -> None:
        """Its path is an opaque share id, not the document's, and must not match."""

        assert handoffs.keys_for_url("https://contoso.sharepoint.com/:w:/s/Policy/EWabc") == set()

    def test_the_stored_keys_meet_every_form_word_reports(self) -> None:
        keys = set(handoffs.document_keys(ITEM, LIBRARY))

        for reported in (
            ITEM["webUrl"],
            f"{LIBRARY}/Reports/Draft%20v3.docx",
            "https://contoso.sharepoint.com/sites/Policy/Shared Documents/Reports/Draft v3.docx",
        ):
            assert keys & handoffs.keys_for_url(reported), reported

    def test_without_the_library_the_unique_id_still_matches(self) -> None:
        assert handoffs.document_keys(ITEM, None) == [f"guid:{GUID.lower()}"]

    def test_a_document_at_the_library_root(self) -> None:
        item = {**ITEM, "parentReference": {"path": "/drives/b!x/root:"}}
        keys = set(handoffs.document_keys(item, LIBRARY))

        assert keys & handoffs.keys_for_url(f"{LIBRARY}/Draft%20v3.docx")


class TestSplittingByDocument:
    def test_a_handoff_for_another_document_is_still_returned(self) -> None:
        mine = stored(handoffs.document_keys(ITEM, LIBRARY))
        other = stored(["guid:00000000-0000-0000-0000-000000000000"])

        here, elsewhere = handoffs.split_by_document([mine, other], ITEM["webUrl"])

        assert [view.id for view in here] == [mine.id]
        assert [view.id for view in elsewhere] == [other.id]
        assert here[0].items.comments[0].quote == "the words"


class TestStoring:
    @pytest.mark.asyncio
    async def test_storing_also_sweeps_old_handoffs(self) -> None:
        session = session_returning()
        with patch.object(handoffs, "get_async_db_session", return_value=session):
            await handoffs.create(
                requester=Requester(oid="oid-ana", tid="tid-contoso", upn="ana@contoso.com"),
                document_name="Draft v3.docx",
                document_url=ITEM["webUrl"],
                keys=["guid:x"],
                items=HandoffItems(comments=[HandoffComment(quote="abc", comment="c")]),
                reference={"serviceUrl": "https://smba"},
            )

        sql = statements(session)
        assert sql[0].startswith("insert into microsoft_word_handoffs")
        assert sql[1].startswith("delete from microsoft_word_handoffs")
        session.commit.assert_awaited_once()
        values = session.execute.await_args_list[0][0][0].compile().params
        assert values["requested_by_oid"] == "oid-ana"
        assert values["requested_by_tid"] == "tid-contoso"
        assert values["requested_by_upn"] == "ana@contoso.com"


class TestListing:
    @pytest.mark.asyncio
    async def test_pending_handoffs_are_looked_up_by_account(self) -> None:
        row = stored(["guid:x"])
        result = MagicMock()
        result.scalars.return_value.all.return_value = [row]
        session = session_returning()
        session.execute = AsyncMock(return_value=result)
        with patch.object(handoffs, "get_async_db_session", return_value=session):
            found = await handoffs.pending_for(ANA)

        assert found == [row]
        (sql,) = statements(session)
        assert "requested_by_oid" in sql and "requested_by_tid" in sql and "status" in sql

    def test_a_url_with_no_host_identifies_nothing(self) -> None:
        assert handoffs.keys_for_url("not a url") == set()


class TestFinishing:
    @pytest.mark.asyncio
    async def test_it_is_one_update_scoped_to_the_asker_and_still_pending(self) -> None:
        session = session_returning(first=("Draft v3.docx", {"serviceUrl": "https://smba"}))
        outcome = HandoffOutcome(
            items=[ItemOutcome(kind="edit", quote="abc", applied=True)]
        )
        with patch.object(handoffs, "get_async_db_session", return_value=session):
            finished = await handoffs.finish(uuid.uuid4(), ANA, "applied", outcome)

        (sql,) = statements(session)
        assert sql.startswith("update microsoft_word_handoffs")
        assert "requested_by_oid" in sql and "requested_by_tid" in sql
        assert "status" in sql and "returning" in sql
        assert finished is not None and finished.document_name == "Draft v3.docx"

    @pytest.mark.asyncio
    async def test_someone_elses_or_a_closed_handoff_is_none(self) -> None:
        session = session_returning(first=None)
        with patch.object(handoffs, "get_async_db_session", return_value=session):
            assert await handoffs.finish(uuid.uuid4(), Account(oid="oid-eve"), "dismissed") is None


class TestTheItems:
    def test_count(self) -> None:
        items = HandoffItems(
            comments=[HandoffComment(quote="a b c", comment="x")],
            edits=[HandoffEdit(quote="d e f", replacement="g")],
        )
        assert items.count == 2


class TestTheReport:
    def test_it_names_what_did_not_land_and_why(self) -> None:
        outcome = HandoffOutcome(
            items=[
                ItemOutcome(kind="comment", quote="is the only option", applied=True),
                ItemOutcome(
                    kind="edit",
                    quote="a passage that has since been rewritten entirely by the author",
                    applied=False,
                    detail="the words are no longer in the document",
                ),
            ]
        )
        text = handoffs.report(FinishedHandoff(document_name="Draft.docx", reference={}), outcome)

        assert text.startswith("Applied to **Draft.docx** in Word: 1 of 2")
        assert "no longer in the document" in text
        assert "…" in text, "a long quote is shortened"
