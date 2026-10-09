"""Tests for the edge cases of writing comments and tracked changes into markup.

The happy paths run through the routes in ``tests/unit/test_word_endpoints.py``. What is
pinned here is every way a write is declined: nothing to anchor to, a quote docx-editor
cannot place, and above all a change that rejecting would not undo, which must never be
handed back to Word.
"""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from docx import Document as NewDocument
from docx_editor.exceptions import DocxEditError, TextNotFoundError

from lib.services.microsoft.word import markup_writes
from lib.services.microsoft.word.markup_writes import EditToApply
from lib.services.microsoft.word.word_package import FragmentError, from_docx

CLAIM = "Our results prove the hypothesis conclusively."


def package(*paragraphs: str) -> str:
    with tempfile.TemporaryDirectory() as work:
        document = NewDocument()
        for text in paragraphs:
            document.add_paragraph(text)
        path = Path(work) / "source.docx"
        document.save(str(path))
        return from_docx(path)


class TestAnchoringAComment:
    def test_a_paragraph_with_no_text_gets_no_comment(self) -> None:
        placed = markup_writes.add_comment(package(""), "a point", None)

        assert placed.anchored is False
        assert placed.detail == markup_writes.NO_TEXT

    def test_a_quote_that_is_not_there_falls_back_to_the_paragraph(self) -> None:
        placed = markup_writes.add_comment(package(CLAIM), "a point", "not in it")

        assert placed.anchored is True
        assert placed.ooxml is not None


class TestApplyingEdits:
    def test_a_change_rejecting_would_not_undo_is_withheld(self) -> None:
        """The safety net: altered words nobody asked for means writing nothing."""

        with patch.object(markup_writes, "_rejected_text", return_value="something else"):
            written = markup_writes.apply_edits(
                package(CLAIM), [EditToApply(quote="prove", replacement="support")]
            )

        assert written.applied == 0
        assert written.ooxml is None
        assert written.warnings == ["rejecting the changes would not restore the original"]
        # Each edit says so too: callers report per edit, and none of these landed.
        assert [edit.applied for edit in written.edits] == [False]
        assert "withheld" in written.edits[0].detail

    def test_a_write_that_fails_after_placing_edits_reports_none_as_applied(self) -> None:
        with patch.object(markup_writes, "_rejected_text", side_effect=DocxEditError("boom")):
            written = markup_writes.apply_edits(
                package(CLAIM), [EditToApply(quote="prove", replacement="support")]
            )

        assert written.applied == 0
        assert written.ooxml is None
        assert [edit.applied for edit in written.edits] == [False]

    def test_an_inconclusive_reversibility_check_still_writes(self) -> None:
        with patch.object(markup_writes, "_rejected_text", return_value=None):
            written = markup_writes.apply_edits(
                package(CLAIM), [EditToApply(quote="prove", replacement="support")]
            )

        assert written.applied == 1
        assert written.ooxml is not None


class TestOneEdit:
    def edit(self) -> EditToApply:
        return EditToApply(quote="prove", replacement="support")

    def test_a_search_docx_editor_cannot_run_is_declined(self) -> None:
        document = MagicMock()
        document.find_all.side_effect = DocxEditError("bad search")

        outcome = markup_writes._apply_one(document, self.edit())

        assert outcome.applied is False
        assert "bad search" in outcome.detail

    def test_a_replacement_docx_editor_refuses_is_declined(self) -> None:
        document = MagicMock()
        document.find_all.return_value = [MagicMock()]
        document.replace.side_effect = TextNotFoundError("gone")

        outcome = markup_writes._apply_one(document, self.edit())

        assert outcome.applied is False
        assert "gone" in outcome.detail


class TestTheReversibilityCheck:
    def test_markup_that_cannot_be_reopened_is_inconclusive(self) -> None:
        fragment = MagicMock()
        fragment.serialise.side_effect = FragmentError("cannot serialise")

        assert markup_writes._rejected_text(fragment) is None


class TestCapturingMarkup:
    def test_both_sides_are_captured_when_asked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(markup_writes, "DEBUG_DIR", str(tmp_path))

        markup_writes.apply_edits(
            package(CLAIM), [EditToApply(quote="prove", replacement="support")]
        )

        stages = sorted(path.name.split("-", 1)[1] for path in tmp_path.iterdir())
        assert stages == ["suggest-in.xml", "suggest-out.xml"]

    def test_a_capture_that_cannot_be_written_does_not_stop_the_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocked: Any = tmp_path / "a-file"
        blocked.write_text("not a directory")
        monkeypatch.setattr(markup_writes, "DEBUG_DIR", str(blocked))

        written = markup_writes.apply_edits(
            package(CLAIM), [EditToApply(quote="prove", replacement="support")]
        )

        assert written.applied == 1
