"""Tests for ``offer_changes``, the Teams agent's way of handing work to Word.

What matters: the document is resolved as the asker (so they cannot offer changes to
something they cannot read), the handoff is stored under their identity with the
conversation to report back to, and items that could never be applied are dropped
before anything is stored.
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lib.agents.tools import word_handoff
from lib.services.microsoft.graph.client import GraphError
from lib.services.microsoft.word.handoffs import HandoffComment, HandoffEdit

TOKEN = "a-user-token"
URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"
REFERENCE = {"serviceUrl": "https://smba", "conversation": {"id": "19:x", "tenantId": "tid-contoso"}}
ITEM: dict[str, Any] = {
    "name": "Draft.docx",
    "eTag": '"{546F3FAE-D9FB-457F-A563-D25549EB3601},4"',
    "webUrl": "https://contoso.sharepoint.com/sites/Policy/_layouts/15/Doc.aspx?sourcedoc=x",
    "parentReference": {"driveId": "b!x", "path": "/drives/b!x/root:"},
}


async def offer(comments: list[dict[str, str]], edits: list[dict[str, str]]) -> str:
    tool = word_handoff.offer_changes_for(TOKEN, REFERENCE)
    return str(await tool.ainvoke({"url": URL, "comments": comments, "edits": edits}))


@pytest.fixture
def graph() -> Any:
    with patch.object(word_handoff.client, "resolve", AsyncMock(return_value=ITEM)) as resolve, \
        patch.object(word_handoff.client, "library_url", AsyncMock(return_value="https://contoso.sharepoint.com/sites/Policy/Shared%20Documents")), \
        patch.object(word_handoff.client, "me", AsyncMock(return_value={"id": "oid-ana", "userPrincipalName": "ana@contoso.com", "mail": "Ana.Lima@contoso.com"})), \
        patch.object(word_handoff.handoffs, "create", AsyncMock()) as create:
        yield resolve, create


class TestOffering:
    @pytest.mark.asyncio
    async def test_it_stores_a_handoff_for_the_asker(self, graph: Any) -> None:
        resolve, create = graph

        said = await offer(
            [{"quote": "is the only option", "comment": "Overclaims."}],
            [{"quote": "recieve", "replacement": "receive"}],
        )

        resolve.assert_awaited_once_with(URL, token=TOKEN)
        stored = create.await_args.kwargs
        assert stored["requester"].oid == "oid-ana"
        assert stored["requester"].tid == "tid-contoso", "the tenant comes from the Teams conversation"
        assert stored["requester"].upn == "ana@contoso.com"
        assert stored["reference"] == REFERENCE
        assert stored["items"].count == 2
        assert any(key.startswith("guid:") for key in stored["keys"])
        assert any(key.startswith("path:") for key in stored["keys"])
        assert "1 comment(s) and 1 tracked change(s)" in said

    @pytest.mark.asyncio
    async def test_nothing_usable_stores_nothing(self, graph: Any) -> None:
        _, create = graph

        said = await offer([], [{"quote": "same words", "replacement": "same words"}])

        create.assert_not_awaited()
        assert said.startswith("Nothing was saved")

    @pytest.mark.asyncio
    async def test_a_document_they_cannot_read_is_refused(self, graph: Any) -> None:
        resolve, create = graph
        resolve.side_effect = GraphError("403")

        said = await offer([{"quote": "the words", "comment": "x"}], [])

        create.assert_not_awaited()
        assert "could not save" in said


    @pytest.mark.asyncio
    async def test_a_document_that_cannot_be_identified_is_refused(self, graph: Any) -> None:
        resolve, create = graph
        resolve.return_value = {"name": "Draft.docx"}

        with patch.object(word_handoff.client, "library_url", AsyncMock(return_value=None)):
            said = await offer([{"quote": "the words", "comment": "x"}], [])

        create.assert_not_awaited()
        assert "could not be identified" in said


class TestUsableItems:
    def test_two_edits_on_the_same_words_keep_the_first(self) -> None:
        items = word_handoff.usable_items(
            [],
            [
                HandoffEdit(quote="The  Results", replacement="the results"),
                HandoffEdit(quote="the results", replacement="our results"),
            ],
        )
        assert [edit.replacement for edit in items.edits] == ["the results"]

    def test_quotes_too_short_to_find_are_dropped(self) -> None:
        items = word_handoff.usable_items(
            [HandoffComment(quote="a", comment="x")],
            [HandoffEdit(quote="ab", replacement="cd")],
        )
        assert items.count == 0

    def test_it_is_capped(self) -> None:
        many = [HandoffComment(quote=f"quote {i}", comment="x") for i in range(150)]
        assert len(word_handoff.usable_items(many, []).comments) == word_handoff.MAX_COMMENTS
