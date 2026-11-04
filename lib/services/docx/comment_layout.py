"""The text of an issue's Word comment, laid out for a reader in the margin.

The first line names the finding and its check. The next, after a blank line,
says before anything else what became of the issue's proposed edits: in the text as tracked changes,
or not, and why. Then comes the explanation, the suggested action, the edits
themselves and the details. An applied edit is only pointed at, since the
tracked change already shows it; one that is not in the text is given in full.

The text marks `**bold**` and `*italic*` and breaks paragraphs on newlines,
which `comment_markup.write_comment` turns into Word formatting.
"""

from collections.abc import Sequence

from lib.services.docx.comment_markup import comment_markdown, literal, plain_text
from lib.services.docx.edit_notes import EditNote


def _status_line(notes: Sequence[EditNote]) -> str | None:
    """What became of the edits, as the comment's second line."""
    applied = [n for n in notes if n.status == "applied"]
    if not notes:
        return None
    if all(n.status == "skipped" for n in notes):
        return (
            "✎ Proposed edit below"
            if len(notes) == 1
            else f"✎ {len(notes)} proposed edits below"
        )
    if len(applied) == len(notes):
        if len(notes) == 1:
            return f"✎ Tracked change in the text: {notes[0].pointer}"
        return f"✎ {len(notes)} tracked changes in the text, listed below"
    if applied:
        missing = len(notes) - len(applied)
        rest = "the other" if missing == 1 else f"the other {missing}"
        kind = "is a tracked change" if len(applied) == 1 else "are tracked changes"
        return (
            f"⚠ {len(applied)} of {len(notes)} edits {kind} in the text; "
            f"{rest} could not be applied, see below"
        )
    if len(notes) == 1:
        return "⚠ Not applied as a tracked change, see the proposed edit below"
    return f"⚠ None of the {len(notes)} proposed edits could be applied, see below"


def _applied_section(notes: Sequence[EditNote]) -> list[str]:
    """The applied edits, listed when the status line could not name them all."""
    applied = [n for n in notes if n.status == "applied"]
    if not applied or (len(applied) == 1 and len(notes) == 1):
        return []
    lines = ["**Tracked changes:**"]
    for number, note in enumerate(applied, 1):
        rationale = comment_markdown(note.rationale).rstrip(".")
        why = f" ({rationale})" if rationale else ""
        lines.append(f"{number}. {note.pointer}{why}")
    return lines


def _pending_section(notes: Sequence[EditNote]) -> list[str]:
    """The edits that are not in the text, in full, with why they are not."""
    pending = [n for n in notes if n.status != "applied"]
    if not pending:
        return []
    skipped = all(n.status == "skipped" for n in pending)
    lines = ["**Proposed edits:**" if skipped else "**Proposed edits, not applied:**"]
    for note in pending:
        lines.append(f"• {note.fix}")
        if note.rationale:
            lines.append(f"  {comment_markdown(note.rationale)}")
        if note.reason and not skipped:
            lines.append(f"  Not applied: {note.reason}.")
    return lines


def comment_text(
    title: str,
    workflow_name: str | None,
    description: str,
    suggested_action: str | None,
    long_description: str | None,
    notes: Sequence[EditNote] = (),
) -> str:
    """The whole comment for one issue."""
    heading = f"**{literal(plain_text(title))}**"
    if workflow_name:
        heading += f" · {workflow_name}"
    blocks = [heading]
    if status := _status_line(notes):
        blocks.append(status)
    blocks.append(comment_markdown(description))
    if suggested_action:
        blocks.append(f"**Suggested action:** {comment_markdown(suggested_action)}")
    for section in (_applied_section(notes), _pending_section(notes)):
        if section:
            blocks.append("\n".join(section))
    if long_description:
        blocks.append(comment_markdown(long_description))
    return "\n\n".join(blocks)
