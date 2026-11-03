"""Every route the Word add-in calls, under ``/word``.

The add-in's chat with Draft Detective lives in ``word_chat.py`` and is mounted here,
under ``/word/chat``. The routes in this file are ``/features``, and the add-in's side
of stored changes under ``/handoffs``.

The Teams bot cannot write a document, so it stores the comments and edits it was asked
for (``lib/services/microsoft/word/handoffs``). The add-in collects them, writes them
with Word's own API, and reports what landed, which the bot posts back into the Teams
thread. The chat's suggestion cards are handoffs too: they are claimed, reported and
dismissed through the same routes, but never listed by ``GET /handoffs`` and never
posted to Teams. A handoff is released only to the Microsoft account that asked for it.

Every route here is called by the add-in, signed in as a Microsoft account (see
``lib/api/addin_auth.py``), not with an ordinary Draft Detective session.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from lib.api.addin_auth import AddinIdentity, get_addin_identity
from lib.api.routers.microsoft import word_chat
from lib.services.microsoft.teams import bot
from lib.services.microsoft.word import handoffs
from lib.services.microsoft.word.handoffs import (
    Account,
    HandoffView,
    InvalidResults,
    ItemResult,
)

router = APIRouter(prefix="/word", tags=["microsoft", "word"])
router.include_router(word_chat.router)


def _account(caller: AddinIdentity) -> Account:
    return Account(oid=caller.oid, tid=caller.tid)


class AddinFeatures(BaseModel):
    teams: bool = Field(
        description=(
            "Whether this deployment runs the Teams bot, so the pane offers the changes "
            "asked for there"
        )
    )


@router.get("/features", response_model=AddinFeatures)
async def features(
    _caller: AddinIdentity = Depends(get_addin_identity),
) -> AddinFeatures:
    """What the pane offers on this deployment."""

    return AddinFeatures(teams=bot.configured())


class PendingHandoffs(BaseModel):
    here: list[HandoffView] = Field(
        default_factory=list, description="Waiting on the document at this URL"
    )
    elsewhere: list[HandoffView] = Field(
        default_factory=list,
        description="Waiting on other documents, or on this one under a URL not recognised",
    )


class HandoffReport(BaseModel):
    results: list[ItemResult] = Field(
        max_length=500,
        description=(
            "What happened to each stored item, by position (comments first, then "
            "edits). Items left out count as not applied."
        ),
    )


@router.get("/handoffs", response_model=PendingHandoffs)
async def list_pending(
    url: str = Query(description="The document URL Word reports"),
    caller: AddinIdentity = Depends(get_addin_identity),
) -> PendingHandoffs:
    """The signed-in account's open handoffs, split by whether they are for this document."""

    here, elsewhere = handoffs.split_by_document(
        await handoffs.pending_for(_account(caller)), url
    )
    return PendingHandoffs(here=here, elsewhere=elsewhere)


@router.post("/handoffs/{handoff_id}/started", status_code=204)
async def start(
    handoff_id: UUID,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> None:
    """Claim a pending handoff before writing it into the document."""

    if not await handoffs.start(handoff_id, _account(caller)):
        raise HTTPException(status_code=404, detail="No pending handoff with that id")


@router.post("/handoffs/{handoff_id}/applied", status_code=204)
async def report_applied(
    handoff_id: UUID,
    report: HandoffReport,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> None:
    """Close a handoff the add-in has written, and say how it went in Teams."""

    try:
        reported = await handoffs.report_applied(
            handoff_id, _account(caller), report.results
        )
    except InvalidResults as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not reported:
        raise HTTPException(status_code=404, detail="No open handoff with that id")


@router.post("/handoffs/{handoff_id}/dismissed", status_code=204)
async def dismiss(
    handoff_id: UUID,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> None:
    """Close a handoff without applying it. Nothing is posted to Teams."""

    if await handoffs.finish(handoff_id, _account(caller), "dismissed") is None:
        raise HTTPException(status_code=404, detail="No open handoff with that id")
