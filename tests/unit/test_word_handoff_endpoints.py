"""Tests for the add-in's side of Teams handoffs.

The routes are thin, so what is pinned is the contract around them: every lookup is by
the signed-in Microsoft account, reporting a result posts once into the Teams thread
the request came from, and a handoff that is not theirs (or already closed) is a 404
with nothing posted.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from lib.api.addin_auth import AddinIdentity
from lib.api.routers.microsoft import word
from lib.api.routers.microsoft.word import HandoffResult
from lib.services.microsoft.word.handoffs import (
    Account,
    FinishedHandoff,
    HandoffOutcome,
    ItemOutcome,
)

REFERENCE = {
    "serviceUrl": "https://smba.trafficmanager.net/br/",
    "channelId": "msteams",
    "conversation": {"id": "19:x;messageid=1"},
}


ANA = Account(oid="oid-ana", tid="tid-contoso")


def caller() -> AddinIdentity:
    return AddinIdentity(oid=ANA.oid, tid=ANA.tid, email="ana@contoso.com")


def outcome() -> HandoffOutcome:
    return HandoffOutcome(
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


class TestListing:
    @pytest.mark.asyncio
    async def test_it_looks_up_by_the_signed_in_account(self) -> None:
        with patch.object(word.handoffs, "pending_for", AsyncMock(return_value=[])) as pending:
            result = await word.list_pending(url="https://x/doc.docx", caller=caller())

        pending.assert_awaited_once_with(ANA)
        assert result.here == [] and result.elsewhere == []


class TestReporting:
    @pytest.mark.asyncio
    async def test_applying_posts_into_the_thread(self) -> None:
        finished = FinishedHandoff(document_name="Draft.docx", reference=REFERENCE)
        handoff_id = uuid.uuid4()
        with patch.object(word.handoffs, "finish", AsyncMock(return_value=finished)) as finish, \
            patch.object(word.handoffs.bot, "post_later", AsyncMock()) as post:
            await word.report_applied(handoff_id, HandoffResult(outcome=outcome()), caller=caller())

        finish.assert_awaited_once()
        assert finish.await_args is not None and post.await_args is not None
        assert finish.await_args.args[:3] == (handoff_id, ANA, "applied")
        reference, text = post.await_args.args
        assert reference.conversation.id == "19:x;messageid=1"
        assert "1 of 2" in text

    @pytest.mark.asyncio
    async def test_not_theirs_is_a_404_and_posts_nothing(self) -> None:
        with patch.object(word.handoffs, "finish", AsyncMock(return_value=None)), \
            patch.object(word.handoffs.bot, "post_later", AsyncMock()) as post:
            with pytest.raises(HTTPException) as raised:
                await word.report_applied(uuid.uuid4(), HandoffResult(outcome=outcome()), caller=caller())

        assert raised.value.status_code == 404
        post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dismissing_someone_elses_is_a_404(self) -> None:
        with patch.object(word.handoffs, "finish", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as raised:
                await word.dismiss(uuid.uuid4(), caller=caller())

        assert raised.value.status_code == 404

    @pytest.mark.asyncio
    async def test_dismissing_posts_nothing(self) -> None:
        finished = FinishedHandoff(document_name="Draft.docx", reference=REFERENCE)
        with patch.object(word.handoffs, "finish", AsyncMock(return_value=finished)) as finish, \
            patch.object(word.handoffs.bot, "post_later", AsyncMock()) as post:
            await word.dismiss(uuid.uuid4(), caller=caller())

        assert finish.await_args is not None
        assert finish.await_args.args[2] == "dismissed"
        post.assert_not_awaited()
