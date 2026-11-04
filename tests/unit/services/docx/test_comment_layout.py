"""Tests for how an issue's Word comment is laid out.

The line after the title always says what became of the proposed edits; an applied edit
is only pointed at, one that is not in the text is given whole.
"""

from lib.services.docx.comment_layout import comment_text
from lib.services.docx.edit_notes import EditNote


def _note(
    status: str, pointer: str = "“a” → “b”", reason: str | None = None
) -> EditNote:
    return EditNote(
        status=status,  # type: ignore[arg-type]  # a test-only shorthand
        pointer=pointer,
        fix=f"Replace “{pointer}”",
        rationale="Because.",
        reason=reason,
    )


def _layout(*notes: EditNote, action: str | None = None) -> list[str]:
    return comment_text(
        "Wordy Construction", "Concision", "Why.", action, None, notes
    ).split("\n")


def test_one_applied_edit_is_named_on_the_status_line_only():
    lines = _layout(_note("applied", "“build” → “built”"))

    assert lines[:3] == [
        "**Wordy Construction** · Concision",
        "",
        "✎ Tracked change in the text: “build” → “built”",
    ]
    assert not any("Replace" in line or "Tracked changes:" in line for line in lines)


def test_several_applied_edits_are_listed_with_their_rationale():
    lines = _layout(_note("applied", "“x” → “y”"), _note("applied", "deletes “z”"))

    assert lines[2] == "✎ 2 tracked changes in the text, listed below"
    assert lines[-3:] == [
        "**Tracked changes:**",
        "1. “x” → “y” (Because)",
        "2. deletes “z” (Because)",
    ]


def test_an_edit_not_applied_is_given_whole_with_the_reason():
    lines = _layout(_note("not_applied", reason="overlaps another proposed edit"))

    assert lines[2] == "⚠ Not applied as a tracked change, see the proposed edit below"
    assert lines[-4:] == [
        "**Proposed edits, not applied:**",
        "• Replace ““a” → “b””",
        "  Because.",
        "  Not applied: overlaps another proposed edit.",
    ]


def test_a_mix_says_how_many_are_in_the_text():
    lines = _layout(_note("applied"), _note("not_applied", reason="no match"))

    assert lines[2] == (
        "⚠ 1 of 2 edits is a tracked change in the text; the other could not be "
        "applied, see below"
    )
    assert "**Tracked changes:**" in lines
    assert "**Proposed edits, not applied:**" in lines


def test_a_comments_only_export_gives_the_edits_without_alarm():
    lines = _layout(_note("skipped", reason="tracked changes were not requested"))

    assert lines[2] == "✎ Proposed edit below"
    assert "**Proposed edits:**" in lines
    assert not any(line.startswith("  Not applied") for line in lines)


def test_without_edits_there_is_no_status_line_and_the_action_stays():
    lines = _layout(action="Cite a source.")

    assert lines == [
        "**Wordy Construction** · Concision",
        "",
        "Why.",
        "",
        "**Suggested action:** Cite a source.",
    ]
