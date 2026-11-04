"""Tests for handing review work from Teams to the Word add-in.

Two things carry the weight. The add-in recognises a document only by the URL Word
reports, which takes different forms in different clients, so ``keys_for_url`` and
``document_keys`` must meet on at least one key for every form. And the report posted
into Teams is built from the stored items, never from text the add-in sends.

Who a handoff is released to, and that each step happens once, is decided by SQL:
``tests/integration/test_word_handoffs.py`` runs it on Postgres.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.word import handoffs
from lib.services.microsoft.word.handoffs import (
    Account,
    FinishedHandoff,
    HandoffComment,
    HandoffEdit,
    HandoffItems,
    HandoffOutcome,
    InvalidResults,
    ItemOutcome,
    ItemResult,
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
        created_at=datetime.now(UTC),
    )


ANA = Account(oid="oid-ana", tid="tid-contoso")
ITEMS = HandoffItems(
    comments=[HandoffComment(quote="is the only option", comment="Overclaims.")],
    edits=[HandoffEdit(quote="recieve", replacement="receive")],
)


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

        assert (
            handoffs.keys_for_url("https://contoso.sharepoint.com/:w:/s/Policy/EWabc")
            == set()
        )

    def test_a_url_with_no_host_identifies_nothing(self) -> None:
        assert handoffs.keys_for_url("not a url") == set()

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
        text = handoffs.report(
            FinishedHandoff(document_name="Draft.docx", reference={}), outcome
        )

        assert text.startswith("Applied to **Draft.docx** in Word: 1 of 2")
        assert "no longer in the document" in text
        assert "…" in text, "a long quote is shortened"


class TestBuildingTheOutcome:
    """The report is posted into Teams as the bot, so only stored text may reach it."""

    def test_quotes_and_reasons_come_from_the_server(self) -> None:
        outcome = handoffs.outcome_from(
            ITEMS,
            [
                ItemResult(index=0, applied=True),
                ItemResult(index=1, applied=False, reason="ambiguous"),
            ],
        )

        assert [(item.kind, item.quote, item.applied) for item in outcome.items] == [
            ("comment", "is the only option", True),
            ("edit", "recieve", False),
        ]
        assert outcome.items[1].detail == handoffs.REASONS["ambiguous"]

    def test_an_item_with_no_result_counts_as_not_applied(self) -> None:
        outcome = handoffs.outcome_from(ITEMS, [ItemResult(index=0, applied=True)])

        assert outcome.items[1].applied is False
        assert outcome.items[1].detail == handoffs.REASONS["not_written"]

    @pytest.mark.parametrize(
        "results",
        [[ItemResult(index=2, applied=True)], [ItemResult(index=0, applied=True)] * 2],
        ids=["out of range", "repeated"],
    )
    def test_results_for_other_items_are_refused(
        self, results: list[ItemResult]
    ) -> None:
        with pytest.raises(InvalidResults):
            handoffs.outcome_from(ITEMS, results)


class TestReportingApplied:
    @pytest.mark.asyncio
    async def test_the_report_posted_is_built_from_the_stored_items(self) -> None:
        reference = {
            "serviceUrl": "https://smba",
            "channelId": "msteams",
            "conversation": {"id": "19:x"},
        }
        finished = FinishedHandoff(
            document_name="Draft.docx", reference=reference, items=ITEMS
        )
        with (
            patch.object(handoffs, "_open_items", AsyncMock(return_value=ITEMS)),
            patch.object(
                handoffs, "finish", AsyncMock(return_value=finished)
            ) as finish,
            patch.object(handoffs.bot, "post_later", AsyncMock()) as post,
        ):
            reported = await handoffs.report_applied(
                uuid.uuid4(),
                ANA,
                [
                    ItemResult(index=0, applied=True),
                    ItemResult(index=1, applied=False, reason="not_found"),
                ],
            )

        assert reported is True
        assert finish.await_args is not None and post.await_args is not None
        stored = finish.await_args.args[3]
        assert [item.quote for item in stored.items] == [
            "is the only option",
            "recieve",
        ]
        text = post.await_args.args[1]
        assert "1 of 2" in text and handoffs.REASONS["not_found"] in text

    @pytest.mark.asyncio
    async def test_invalid_results_post_nothing(self) -> None:
        with (
            patch.object(handoffs, "_open_items", AsyncMock(return_value=ITEMS)),
            patch.object(handoffs, "finish", AsyncMock()) as finish,
            patch.object(handoffs.bot, "post_later", AsyncMock()) as post,
        ):
            with pytest.raises(InvalidResults):
                await handoffs.report_applied(
                    uuid.uuid4(), ANA, [ItemResult(index=7, applied=True)]
                )

        finish.assert_not_awaited()
        post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_theirs_or_closed_posts_nothing(self) -> None:
        with (
            patch.object(handoffs, "_open_items", AsyncMock(return_value=None)),
            patch.object(handoffs.bot, "post_later", AsyncMock()) as post,
        ):
            assert await handoffs.report_applied(uuid.uuid4(), ANA, []) is False

        post.assert_not_awaited()


class TestHandoffsFromTheChat:
    @pytest.mark.asyncio
    async def test_applying_one_posts_nothing_to_teams(self) -> None:
        finished = FinishedHandoff(
            document_name="Draft.docx", reference=None, items=ITEMS
        )
        with (
            patch.object(handoffs, "_open_items", AsyncMock(return_value=ITEMS)),
            patch.object(
                handoffs, "finish", AsyncMock(return_value=finished)
            ) as finish,
            patch.object(handoffs.bot, "post_later", AsyncMock()) as post,
        ):
            reported = await handoffs.report_applied(
                uuid.uuid4(), ANA, [ItemResult(index=0, applied=True)]
            )

        assert reported is True
        finish.assert_awaited_once()
        post.assert_not_awaited()
