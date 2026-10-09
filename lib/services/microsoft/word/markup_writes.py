"""Writing Draft Detective's comments and tracked changes into a paragraph's markup.

The add-in sends the Flat OPC of one paragraph (or the outermost table around it), and
gets it back with a comment or tracked changes in it, authored as Draft Detective.
Markup rather than the Word API, because Word authors an API-created comment as
whoever is signed in, with no way to override it, and cannot create a tracked change
at all.

The markup itself is written by ``docx-editor``, reached through
``word_package.editable``. What lives here is the part specific to us: where to anchor
a comment, declining an edit that could land on the wrong words, and refusing to hand
back a change that rejecting would not undo.
"""

import logging
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from docx_editor import Document
from docx_editor.exceptions import (
    AmbiguousTextError,
    DocxEditError,
    TextNotFoundError,
)
from docx_editor.xml_editor import ParagraphInfo
from pydantic import BaseModel, Field

from lib.services.microsoft.word.word_package import Fragment, FragmentError, editable

logger = logging.getLogger(__name__)

# Set DD_COMMENT_DEBUG_DIR to capture the markup on the way in and on the way out.
# Word answers a package it dislikes with GeneralException and no detail, so having
# the actual bytes is the only reliable way to find out what it objected to.
DEBUG_DIR = os.getenv("DD_COMMENT_DEBUG_DIR")

NO_TEXT = "This paragraph has no text to anchor a comment to"


class CommentPlacement(BaseModel):
    anchored: bool
    ooxml: Optional[str] = Field(
        default=None, description="The markup to put back, when we anchored"
    )
    comment_id: Optional[str] = None
    detail: str = ""


class EditToApply(BaseModel):
    quote: str = Field(description="The exact words to change, verbatim")
    replacement: str = Field(description="What they become. Empty removes them.")


class AppliedEdit(BaseModel):
    applied: bool
    quote: str
    detail: str = ""
    revision_ids: list[int] = Field(default_factory=list)


class EditsWritten(BaseModel):
    applied: int = Field(description="How many changes were written")
    ooxml: Optional[str] = Field(
        default=None, description="The markup to put back, when anything was written"
    )
    edits: list[AppliedEdit] = Field(default_factory=list)
    detail: str = ""
    warnings: list[str] = Field(
        default_factory=list,
        description="Why a change was withheld, when it was",
    )


def add_comment(ooxml: str, comment: str, quote: Optional[str]) -> CommentPlacement:
    """Write one Draft Detective comment into this paragraph's markup.

    Mechanical: no model call, and it touches only its own paragraph, so placing
    several comments never rewrites a long document whole.
    """

    try:
        with editable(ooxml) as fragment:
            document = fragment.document
            anchor = _anchor_for(quote, document.list_paragraphs_structured())
            if anchor is None:
                return CommentPlacement(anchored=False, detail=NO_TEXT)
            comment_id = document.add_comment(anchor, comment)
            outgoing = fragment.serialise()
    except (FragmentError, DocxEditError) as error:
        logger.error("could not anchor a comment: %s", error)
        return CommentPlacement(
            anchored=False, detail="The comment could not be written into this markup"
        )

    return CommentPlacement(
        anchored=True, ooxml=outgoing, comment_id=str(comment_id), detail="Comment anchored"
    )


def _anchor_for(quote: Optional[str], paragraphs: list[ParagraphInfo]) -> Optional[str]:
    """The text to anchor a comment to: the phrase if it is there, else the paragraph.

    A quote that cannot be found is not a reason to say nothing. The point being
    raised is about this paragraph either way, so the whole paragraph is the
    fallback rather than silence.
    """

    with_text = [info for info in paragraphs if info.text.strip()]
    if not with_text:
        return None
    if quote and quote.strip():
        wanted = quote.strip()
        for info in with_text:
            if wanted in info.text:
                return wanted
    return with_text[0].text.strip()


def apply_edits(ooxml: str, edits: list[EditToApply]) -> EditsWritten:
    """Write proposed changes into this paragraph as tracked changes.

    Takes every change for one paragraph together. Each write is a chance for Word
    to reject the package, so a paragraph with three changes is one read, one call
    and one write rather than three of each.
    """

    reference = uuid4().hex[:8]
    _capture("suggest-in", ooxml, reference)

    outcomes: list[AppliedEdit] = []
    try:
        with editable(ooxml) as fragment:
            document = fragment.document
            # what the paragraph says today, to prove afterwards that rejecting
            # every change we write puts it back exactly as it was
            original = _visible_text(document)
            outcomes = [_apply_one(document, edit) for edit in edits]
            applied = sum(1 for outcome in outcomes if outcome.applied)
            if not applied:
                return EditsWritten(
                    applied=0, edits=outcomes, detail="No change could be placed here"
                )
            restored = _rejected_text(fragment)
            outgoing = fragment.serialise()
    except (FragmentError, DocxEditError) as error:
        logger.error("could not apply changes: %s", error)
        return EditsWritten(
            applied=0,
            edits=_withheld(outcomes, "the paragraph could not be written"),
            detail="The changes could not be written into this markup",
        )

    # Rejecting everything we wrote must reproduce the paragraph we were given. If
    # it does not, we have altered words nobody asked us to, and the safe move is
    # to write nothing at all rather than hand Word a mangled document.
    if restored is not None and restored != original:
        logger.error(
            "refusing to write: rejecting these changes would not restore the original text"
        )
        return EditsWritten(
            applied=0,
            edits=_withheld(outcomes, "withheld: rejecting it would not restore the original text"),
            detail="The change would have altered text it should not have",
            warnings=["rejecting the changes would not restore the original"],
        )

    _capture("suggest-out", outgoing, reference)
    return EditsWritten(
        applied=applied,
        ooxml=outgoing,
        edits=outcomes,
        detail=f"Wrote {applied} tracked change(s)",
    )


def _withheld(outcomes: list[AppliedEdit], reason: str) -> list[AppliedEdit]:
    """The outcomes of a write that was not handed back: none of them landed.

    Each edit was placed in the working copy, but that copy is discarded, so an edit
    reported as applied here would tell the author about a tracked change that is not
    in their document.
    """

    return [
        outcome.model_copy(update={"applied": False, "detail": reason, "revision_ids": []})
        if outcome.applied
        else outcome
        for outcome in outcomes
    ]


def _apply_one(document: Document, edit: EditToApply) -> AppliedEdit:
    """One proposed change, refused rather than approximated.

    A comment anchored to the wrong one of two identical phrases costs precision.
    An edit applied to the wrong one changes the wrong words, so an ambiguous
    quote is declined instead of guessed at.
    """

    try:
        matches = document.find_all(edit.quote)
    except DocxEditError as error:
        return AppliedEdit(applied=False, quote=edit.quote, detail=str(error))

    if not matches:
        return AppliedEdit(
            applied=False,
            quote=edit.quote,
            detail="Those exact words are not in this paragraph",
        )
    if len(matches) > 1:
        return AppliedEdit(
            applied=False,
            quote=edit.quote,
            detail=f"Those words appear {len(matches)} times here, so which one is unclear",
        )

    match = matches[0]
    try:
        # paragraph_occurrence bridges the two counts: find_all counts matches
        # across the fragment, while replace counts them within one paragraph.
        result = document.replace(
            edit.quote,
            edit.replacement,
            paragraph=match.paragraph_ref,
            occurrence=match.paragraph_occurrence,
        )
    except (AmbiguousTextError, TextNotFoundError) as error:
        return AppliedEdit(applied=False, quote=edit.quote, detail=str(error))

    return AppliedEdit(
        applied=True,
        quote=edit.quote,
        revision_ids=list(getattr(result, "revision_ids", ()) or ()),
    )


def _visible_text(document: Document) -> str:
    """The paragraphs as they read now, for comparing before against after."""

    return "\n".join(info.text for info in document.list_paragraphs_structured())


def _rejected_text(fragment: Fragment) -> Optional[str]:
    """What the text would say if the author rejected every change we just wrote.

    Checked on a throwaway copy: rejecting for real would undo the work. Returns
    None when the check cannot be made, which is treated as inconclusive rather
    than as a failure.
    """

    try:
        markup = fragment.serialise()
        with editable(markup) as copy:
            copy.document.reject_all()
            return _visible_text(copy.document)
    except (FragmentError, DocxEditError) as error:
        logger.warning("could not verify the changes are reversible: %s", error)
        return None


def _capture(stage: str, markup: str, reference: str) -> None:
    if not DEBUG_DIR:
        return
    try:
        directory = Path(DEBUG_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{reference}-{stage}.xml"
        path.write_text(markup, encoding="utf-8")
        logger.info("captured %s markup (%s chars) at %s", stage, len(markup), path)
    except OSError as error:
        logger.warning("could not capture %s markup: %s", stage, error)
