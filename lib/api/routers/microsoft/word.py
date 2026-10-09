"""Draft Detective writing into a Word document, through the add-in.

The add-in sends the markup of one paragraph and gets it back with a comment
(``/comments/annotate``) or tracked changes (``/suggestions/apply``) written in, both
authored as Draft Detective -- see ``lib/services/microsoft/word/markup_writes.py``.

Changes asked for in Teams arrive here too, under ``/handoffs``: the bot cannot write a
document, so it stores the comments and edits (``lib/services/microsoft/word/handoffs``)
and the add-in collects them, writes them through the routes above, and reports what
landed, which the bot posts back into the Teams thread. Those routes are scoped to the
signed-in Microsoft account: a handoff is released only to the account that asked for it.

Every route here is called by the add-in, signed in as a Microsoft account (see
``lib/api/addin_auth.py``), not with an ordinary Draft Detective session.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from lib.api.addin_auth import AddinIdentity, get_addin_identity
from lib.services.microsoft.word import handoffs, markup_writes
from lib.services.microsoft.word.handoffs import Account, HandoffOutcome, HandoffView
from lib.services.microsoft.word.markup_writes import (
    CommentPlacement,
    EditsWritten,
    EditToApply,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/word", tags=["microsoft", "word"])

MAX_MARKUP_CHARS = 8_000_000

# Both write routes take the markup of one paragraph, or the outermost table around it.
SCOPE = (
    "the paragraph, or the whole outermost table when it is inside one. Write the "
    "result back at the same scope it was read at."
)


def _account(caller: AddinIdentity) -> Account:
    return Account(oid=caller.oid, tid=caller.tid)


def _too_large(markup: str) -> None:
    if len(markup) > MAX_MARKUP_CHARS:
        raise HTTPException(
            status_code=413, detail=f"Markup exceeds {MAX_MARKUP_CHARS} characters"
        )


class AnnotateRequest(BaseModel):
    ooxml: str = Field(description=f"Flat OPC markup for the range the comment belongs on: {SCOPE}")
    quote: Optional[str] = Field(
        default=None,
        description=(
            "Optionally the phrase within this paragraph to highlight, verbatim. "
            "Omitted, or not found, anchors the comment to the whole paragraph."
        ),
    )
    comment: str = Field(description="What to say about it")


@router.post("/comments/annotate", response_model=CommentPlacement)
async def annotate(
    request: AnnotateRequest,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> CommentPlacement:
    """Write one Draft Detective comment into this paragraph's markup."""

    _too_large(request.ooxml)
    placed = markup_writes.add_comment(request.ooxml, request.comment, request.quote)
    if not placed.anchored:
        logger.info("no comment anchored for account %s: %s", caller.oid, placed.detail)
    return placed


class ApplySuggestionsRequest(BaseModel):
    ooxml: str = Field(description=f"Flat OPC markup for the range to change: {SCOPE}")
    edits: list[EditToApply] = Field(
        description=(
            "Every change for this one paragraph, applied in one pass, so the "
            "caller reads and writes the paragraph once however many there are."
        )
    )


@router.post("/suggestions/apply", response_model=EditsWritten)
async def apply_suggestions(
    request: ApplySuggestionsRequest,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> EditsWritten:
    """Write Draft Detective's proposed changes into this paragraph as tracked changes."""

    _too_large(request.ooxml)
    written = markup_writes.apply_edits(request.ooxml, request.edits)
    logger.info(
        "applied %s of %s change(s) for account %s", written.applied, len(request.edits), caller.oid
    )
    return written


class PendingHandoffs(BaseModel):
    here: list[HandoffView] = Field(
        default_factory=list, description="Waiting on the document at this URL"
    )
    elsewhere: list[HandoffView] = Field(
        default_factory=list,
        description="Waiting on other documents, or on this one under a URL not recognised",
    )


class HandoffResult(BaseModel):
    outcome: HandoffOutcome


@router.get("/handoffs", response_model=PendingHandoffs)
async def list_pending(
    url: str = Query(description="The document URL Word reports"),
    caller: AddinIdentity = Depends(get_addin_identity),
) -> PendingHandoffs:
    """The signed-in account's pending handoffs, split by whether they are for this document."""

    here, elsewhere = handoffs.split_by_document(await handoffs.pending_for(_account(caller)), url)
    return PendingHandoffs(here=here, elsewhere=elsewhere)


@router.post("/handoffs/{handoff_id}/applied", status_code=204)
async def report_applied(
    handoff_id: UUID,
    result: HandoffResult,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> None:
    """Close a handoff the add-in has written, and say how it went in Teams."""

    if not await handoffs.report_applied(handoff_id, _account(caller), result.outcome):
        raise HTTPException(status_code=404, detail="No pending handoff with that id")


@router.post("/handoffs/{handoff_id}/dismissed", status_code=204)
async def dismiss(
    handoff_id: UUID,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> None:
    """Close a handoff without applying it. Nothing is posted to Teams."""

    if await handoffs.finish(handoff_id, _account(caller), "dismissed") is None:
        raise HTTPException(status_code=404, detail="No pending handoff with that id")
