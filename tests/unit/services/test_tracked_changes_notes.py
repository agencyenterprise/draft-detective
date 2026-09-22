"""Tests for what a Word comment says about each proposed edit.

Every edit the export considered is written into its issue's comment, whether
or not it became a redline; these are the sentences that say which.
"""

import uuid

import pytest

from lib.models.issue_edit import IssueEditStatus
from lib.services.docx.edit_notes import build_edit_notes
from lib.services.docx.tracked_changes import EditOutcome

from tests.unit.services.tracked_changes_support import (
    make_edit as _edit,
)


class TestEditNotes:
    def test_an_applied_edit_reads_as_a_tracked_change(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="applied")}, {}
        )

        assert note == (
            'Proposed edit: "14% rise" → "18% rise"\n'
            "because the figure is misnumbered\n"
            "Applied below as a tracked change."
        )

    def test_a_deletion_is_labelled_as_one(self):
        edit = _edit("for 2019", "", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="applied")}, {}
        )

        assert note.startswith('Proposed deletion: "for 2019"\n')

    def test_a_conflict_names_the_workflow_it_lost_to(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit],
            {edit.id: EditOutcome(edit_id=edit.id, status="conflict")},
            {edit.id: "Reference Error Checker"},
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "on this line (Reference Error Checker)."
        )

    def test_a_conflict_without_a_named_winner_says_so_plainly(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="conflict")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "in the same paragraph."
        )

    def test_an_unsupported_replacement_says_what_word_cannot_show(self):
        edit = _edit("aword", "a\nword", 1)

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="unsupported",
                    detail="the replacement spans more than one paragraph",
                )
            },
            {},
        )

        assert note.endswith(
            "Not applied as a tracked change: the replacement cannot be "
            "represented in Word (the replacement spans more than one "
            "paragraph)."
        )

    def test_an_unsupported_replacement_without_a_detail_stops_at_the_reason(self):
        edit = _edit("aword", "a\nword", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="unsupported")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: the replacement cannot be "
            "represented in Word."
        )

    def test_a_paragraph_wide_conflict_says_which_paragraph_it_is(self):
        edit = _edit("14% rise", "18% rise", 1)
        winner_id = uuid.uuid4()

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="conflict",
                    detail=f"overlaps proposed edit {winner_id} in this paragraph",
                    winner_id=winner_id,
                )
            },
            {edit.id: "Advocacy Tone Check"},
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "in this paragraph (Advocacy Tone Check)."
        )

    def test_a_failed_write_says_what_went_wrong(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="failed",
                    detail="text not found in paragraph P3#aaaa",
                )
            },
            {},
        )

        assert note.endswith(
            "Not applied as a tracked change: text not found in paragraph " "P3#aaaa."
        )

    def test_a_failed_write_without_a_detail_still_reads_as_a_failure(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="failed")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: writing the change to Word failed."
        )

    @pytest.mark.parametrize("status", ["unlocatable", "not_found", "ambiguous"])
    def test_every_unmatched_outcome_reads_the_same(self, status):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status=status)}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: the quoted text could not be "
            "matched in this paragraph."
        )

    def test_an_edit_with_no_outcome_is_left_out(self):
        edit = _edit("14% rise", "18% rise", 1, status=IssueEditStatus.REJECTED)

        assert build_edit_notes([edit], {}, {}) == []
