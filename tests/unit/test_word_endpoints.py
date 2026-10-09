"""Unit tests for the Word endpoints.

The fixtures are real documents rather than hand-written scraps of markup.
``docx-editor`` opens the package as a .docx, so a package missing
``[Content_Types].xml`` or its relationships is not something it will accept --
and neither is Word, which is the point. Building them from python-docx costs a
little time per module and buys tests that exercise the path the add-in uses.
"""

import tempfile
import uuid
from pathlib import Path

import pytest
from docx import Document as NewDocument
from fastapi import HTTPException

from lib.api.addin_auth import AddinIdentity
from lib.api.routers.microsoft.word import (
    MAX_MARKUP_CHARS,
    AnnotateRequest,
    ApplySuggestionsRequest,
    EditToApply,
    annotate,
    apply_suggestions,
)
from lib.services.microsoft.word.word_package import editable, from_docx

CLAIM = "Our results prove the hypothesis conclusively."


def _package(text: str) -> str:
    """A package shaped like the one an add-in sends for one paragraph."""

    with tempfile.TemporaryDirectory() as work:
        document = NewDocument()
        document.add_paragraph(text)
        path = Path(work) / "source.docx"
        document.save(str(path))
        return from_docx(path)


SUGGESTION_MARKUP = _package(CLAIM)


def _caller() -> AddinIdentity:
    return AddinIdentity(oid=str(uuid.uuid4()), tid=str(uuid.uuid4()))


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_no_route_crashes_on_markup_that_will_not_parse():
    """Garbage in must be a refusal, not a 500.

    ``to_docx`` used to raise a raw lxml error from inside ``editable``, which no
    route caught, so annotate and apply answered with a server error instead of
    saying they could not use the package.
    """

    caller = _caller()
    anchored = await annotate(
        AnnotateRequest(ooxml="<not xml", comment="a note"), caller=caller
    )
    assert anchored.anchored is False
    assert anchored.ooxml is None

    applied = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml="<not xml",
            edits=[EditToApply(quote="prove", replacement="support")],
        ),
        caller=caller,
    )
    assert applied.applied == 0
    assert applied.ooxml is None


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_annotate_authors_the_comment_as_draft_detective():
    """The whole reason annotations go through markup rather than the Word API."""

    response = await annotate(
        AnnotateRequest(
            ooxml=SUGGESTION_MARKUP, quote="prove", comment="This is p95 only."
        ),
        caller=_caller(),
    )

    assert response.anchored is True
    assert response.ooxml is not None
    assert 'w:author="Draft Detective"' in response.ooxml
    assert "This is p95 only." in response.ooxml


@pytest.mark.asyncio
async def test_annotate_falls_back_to_the_paragraph():
    """The caller picked this paragraph, so a bad phrase costs precision only."""

    response = await annotate(
        AnnotateRequest(
            ooxml=SUGGESTION_MARKUP,
            quote="a phrase that is not there",
            comment="note",
        ),
        caller=_caller(),
    )

    assert response.anchored is True
    assert response.ooxml is not None


@pytest.mark.asyncio
async def test_annotate_without_a_quote_anchors_the_paragraph():
    response = await annotate(
        AnnotateRequest(
            ooxml=SUGGESTION_MARKUP, comment="a point about this paragraph"
        ),
        caller=_caller(),
    )
    assert response.anchored is True
    assert response.ooxml is not None


@pytest.mark.asyncio
async def test_applies_a_tracked_change_authored_as_draft_detective():
    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[EditToApply(quote="prove", replacement="support")],
        ),
        caller=_caller(),
    )

    assert response.applied == 1
    assert response.ooxml is not None
    assert 'w:author="Draft Detective"' in response.ooxml
    assert "<w:ins" in response.ooxml and "<w:del" in response.ooxml
    assert response.warnings == [], "a clean apply withholds nothing"
    assert response.edits[0].revision_ids


@pytest.mark.asyncio
async def test_applies_several_changes_to_one_paragraph_in_one_pass():
    """One read and one write per paragraph, however many changes it carries."""

    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[
                EditToApply(quote="prove", replacement="support"),
                EditToApply(quote=" conclusively", replacement=""),
            ],
        ),
        caller=_caller(),
    )

    assert response.applied == 2
    assert response.ooxml is not None


@pytest.mark.asyncio
async def test_writes_nothing_when_no_change_can_be_placed():
    """The caller must not spend a write that cannot achieve anything."""

    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[EditToApply(quote="a phrase that is absent", replacement="x")],
        ),
        caller=_caller(),
    )

    assert response.applied == 0
    assert response.ooxml is None
    assert "not in this paragraph" in response.edits[0].detail


@pytest.mark.asyncio
async def test_an_ambiguous_quote_is_refused_rather_than_guessed():
    """Editing the wrong one of two identical phrases changes the wrong words."""

    ambiguous = _package("The rate rose. The rate fell.")
    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=ambiguous,
            edits=[EditToApply(quote="The rate", replacement="The ratio")],
        ),
        caller=_caller(),
    )

    assert response.applied == 0
    assert response.ooxml is None
    assert "unclear" in response.edits[0].detail


@pytest.mark.asyncio
async def test_a_partial_batch_still_returns_the_markup():
    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[
                EditToApply(quote="prove", replacement="support"),
                EditToApply(quote="not present here", replacement="x"),
            ],
        ),
        caller=_caller(),
    )

    assert response.applied == 1
    assert response.ooxml is not None
    assert [edit.applied for edit in response.edits] == [True, False]


@pytest.mark.asyncio
async def test_rejecting_the_changes_restores_the_original_wording():
    """The safety check the route makes before it writes anything."""

    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[EditToApply(quote="prove", replacement="support")],
        ),
        caller=_caller(),
    )

    assert response.applied == 1
    assert response.ooxml is not None
    with editable(response.ooxml) as fragment:
        fragment.document.reject_all()
        restored = " ".join(
            info.text for info in fragment.document.list_paragraphs_structured()
        )
    assert restored == CLAIM, "rejecting must put back exactly what was there"


@pytest.mark.asyncio
async def test_accepting_the_changes_gives_the_new_wording():
    response = await apply_suggestions(
        ApplySuggestionsRequest(
            ooxml=SUGGESTION_MARKUP,
            edits=[EditToApply(quote="prove", replacement="support")],
        ),
        caller=_caller(),
    )

    assert response.ooxml is not None
    with editable(response.ooxml) as fragment:
        fragment.document.accept_all()
        accepted = " ".join(
            info.text for info in fragment.document.list_paragraphs_structured()
        )
    assert accepted == "Our results support the hypothesis conclusively."


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_oversized_suggestion_markup_is_rejected():
    with pytest.raises(HTTPException) as error:
        await apply_suggestions(
            ApplySuggestionsRequest(
                ooxml="x" * (MAX_MARKUP_CHARS + 1),
                edits=[EditToApply(quote="prove", replacement="support")],
            ),
            caller=_caller(),
        )
    assert error.value.status_code == 413
