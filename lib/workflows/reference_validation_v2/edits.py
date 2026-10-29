"""Tracked-change edits for a reference the validator could correct with confidence.

The validator returns a corrected copy of the reference. The difference between
the two, word by word, gives the edits: each run of changed words becomes one
small replacement ("Elliahou" -> "Eliahou") rather than the whole reference
being struck and retyped, so an author reviewing the redline sees only what is
wrong.

An edit is proposed only where the fix is not in doubt:

- the reference was found and has at least one field marked incorrect, with a
  source URL behind it. A missing field would need an insertion whose place in
  the citation style is a guess, so it stays a suggested action, also when the
  validator writes it into a change next to an incorrect field;
- the corrected reference keeps most of the original's words, since a rewrite
  of most of a citation is a judgment call for the author, not a redline;
- every word a change touches lies where a field marked incorrect sits in the
  reference (for an insertion, the word it is inserted next to, as when
  co-authors are added to an author list). The validator sometimes restyles a
  field it marked correct (a title's capitalization, a URL's form); those
  changes are dropped;
- the quoted text is found once on the reference's own line of the document.

A change is widened until its quote is unique on the line, so two widened
changes can reach the same words. Those are merged into one edit: two edits
sharing a word would conflict in the export, and only one would be applied.
"""

import difflib
from collections.abc import Sequence

from pydantic import BaseModel

from lib.agents.reference_validator_v2 import (
    BibliographyFieldValidationV2,
    BibliographyItemValidationV2,
    FieldProblemTypeV2,
    ReferenceValidationFinalResultV2,
)
from lib.workflows.models import ProposedEdit
from lib.workflows.simple_deep_agent.edit_anchoring import find_quote_lines
from lib.workflows.simple_deep_agent.issue_reporting import (
    ProposedEditInput,
    resolve_edit,
)

# The share of the original's words the corrected reference must keep. Below
# it the correction is a rewrite (a whole author list and venue swapped).
_MIN_WORDS_KEPT = 0.6

# More changed runs than this is also a rewrite, however short each one is.
_MAX_EDITS = 4

_EDGE_PUNCTUATION = "\"'“”‘’,.;:()[]"

# Words this short ("and", "of", "the") say nothing about where a field sits.
_SHORT_WORD = 3

# Words of one field restated in another order sit at most this far apart.
_RUN_GAP = 3


class _WordChange(BaseModel):
    """One run of changed words, as word indices into the original."""

    start: int
    end: int
    replacement: list[str]


class _Quote(BaseModel):
    """A stretch of the original's words to quote, with the changes inside it."""

    start: int
    end: int
    changes: list[_WordChange]


def build_reference_edits(
    result: BibliographyItemValidationV2,
    reference_text: str,
    lines: Sequence[str],
    start_line: int,
    end_line: int,
) -> list[ProposedEdit]:
    """The edits that turn the cited reference into the validator's correction."""
    incorrect = _incorrect_fields(result)
    if not _is_confident(result, incorrect):
        return []

    original = reference_text.split()
    corrected = (result.updated_reference or "").split()
    matcher = difflib.SequenceMatcher(a=original, b=corrected, autojunk=False)
    kept = sum(block.size for block in matcher.get_matching_blocks())
    if not original or kept / len(original) < _MIN_WORDS_KEPT:
        return []

    runs = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if len(runs) > _MAX_EDITS:
        return []
    # Missing values are looked for in the whole run, before it is split: split
    # word by word, a value of several words would pass one word at a time.
    missing = _missing_values(result)
    changes = [
        change
        for _, i1, i2, j1, j2 in runs
        if not _adds_missing(
            _WordChange(start=i1, end=i2, replacement=corrected[j1:j2]),
            original,
            missing,
        )
        for change in _split(original[i1:i2], corrected[j1:j2], i1)
    ]

    # The other fields' places come first, so an incorrect field restated in
    # another order cannot be placed across one of them. Only a place that is
    # certain counts: a value found once, word for word. A year can also sit
    # inside a title, and claiming the title's copy would block its fix.
    taken = [
        span
        for f in result.bibliography_field_validations
        if f not in incorrect and (span := _unique_exact_span(f, original))
    ]
    spans = [span for f in incorrect if (span := _field_span(f, original, taken))]
    quotes = [
        quote
        for change in (_anchored(c, original, spans) for c in changes)
        if _inside(_touched(change), original, spans)
        and (quote := _unique_quote(change, original, lines, start_line, end_line))
    ]
    return [
        edit
        for quote in _merged(quotes)
        if (edit := _edit(quote, original, lines, start_line, end_line))
    ]


def _split(old: list[str], new: list[str], start: int) -> list[_WordChange]:
    """One run of changed words, split word for word when both sides are as long.

    The diff joins neighbouring changes into one run ("John. Brown" to "Joan.
    BROWN"), which may span a field marked incorrect and one marked correct.
    Split, each word is judged by the field it sits in.
    """
    if len(old) != len(new):
        return [_WordChange(start=start, end=start + len(old), replacement=new)]
    return [
        _WordChange(start=start + i, end=start + i + 1, replacement=[b])
        for i, (a, b) in enumerate(zip(old, new, strict=True))
        if a != b
    ]


def _incorrect_fields(
    result: BibliographyItemValidationV2,
) -> list[BibliographyFieldValidationV2]:
    return [
        field
        for field in result.bibliography_field_validations
        if field.problem_type == FieldProblemTypeV2.INCORRECT
    ]


def _is_confident(
    result: BibliographyItemValidationV2,
    incorrect: list[BibliographyFieldValidationV2],
) -> bool:
    return (
        result.final_result == ReferenceValidationFinalResultV2.INCORRECT_FIELDS
        and bool(incorrect)
        and bool(result.url.strip())
        and bool((result.updated_reference or "").strip())
    )


def _normalized(word: str) -> str:
    return word.strip(_EDGE_PUNCTUATION).lower()


def _field_span(
    field: BibliographyFieldValidationV2,
    original: list[str],
    taken: Sequence[tuple[int, int]] = (),
) -> tuple[int, int] | None:
    """Where a field's cited value sits in the reference, as word indices.

    The validator usually copies the value as cited, but it may restate it in
    another order ("Dylan Patel" for "Patel, Dylan"). Then the span is the
    densest run of the value's longer words, so a short word such as "and"
    elsewhere in the reference cannot place the field there. Neither way may
    the span reach into `taken`, the places of the other fields.
    """
    words = [w for w in map(_normalized, field.current_value.split()) if w]
    norm = [_normalized(w) for w in original]
    if not words:
        return None

    def free(start: int, end: int) -> bool:
        return all(end <= a or start >= b for a, b in taken)

    for i in range(len(norm) - len(words) + 1):
        if norm[i : i + len(words)] == words and free(i, i + len(words)):
            return i, i + len(words)
    distinctive = {w for w in words if len(w) > _SHORT_WORD}
    hits = [i for i, w in enumerate(norm) if w in distinctive and free(i, i + 1)]
    runs: list[list[int]] = []
    for i in hits:
        if runs and i - runs[-1][-1] <= _RUN_GAP and free(runs[-1][0], i + 1):
            runs[-1].append(i)
        else:
            runs.append([i])
    best = max(runs, key=len, default=None)
    return (best[0], best[-1] + 1) if best else None


def _unique_exact_span(
    field: BibliographyFieldValidationV2, original: list[str]
) -> tuple[int, int] | None:
    """Where a field's value appears word for word, if it appears exactly once."""
    words = [w for w in map(_normalized, field.current_value.split()) if w]
    norm = [_normalized(w) for w in original]
    found = [
        i
        for i in range(len(norm) - len(words) + 1)
        if words and norm[i : i + len(words)] == words
    ]
    return (found[0], found[0] + len(words)) if len(found) == 1 else None


def _anchored(
    change: _WordChange, original: list[str], spans: list[tuple[int, int]]
) -> _WordChange:
    """An insertion, as a replacement of the neighbour it is inserted beside.

    The neighbour is the one inside an incorrect field, so a word added at the
    start of an incorrect title that follows a correct author ("Smith. Study."
    to "Smith. A Study.") is anchored on the title, not on the author.
    """
    if change.start < change.end:
        return change
    at = change.start

    def inside(i: int) -> bool:
        return any(start <= i < end for start, end in spans)

    if at > 0 and (inside(at - 1) or at == len(original)):
        return _WordChange(
            start=at - 1, end=at, replacement=[original[at - 1], *change.replacement]
        )
    if at < len(original):
        return _WordChange(
            start=at, end=at + 1, replacement=[*change.replacement, original[at]]
        )
    return change


def _touched(change: _WordChange) -> range:
    """The original's words a change replaces, or for an insertion its neighbour."""
    if change.start < change.end:
        return range(change.start, change.end)
    neighbour = change.start - 1 if change.start > 0 else change.start
    return range(neighbour, neighbour + 1)


def _inside(indices: range, original: list[str], spans: list[tuple[int, int]]) -> bool:
    """Whether every touched word (punctuation aside) lies in an incorrect field."""
    return all(
        any(start <= i < end for start, end in spans)
        for i in indices
        if _normalized(original[i])
    )


def _missing_values(result: BibliographyItemValidationV2) -> list[set[str]]:
    """The words of each missing field's value, as the source gives it."""
    return [
        words
        for field in result.bibliography_field_validations
        if field.problem_type == FieldProblemTypeV2.MISSING
        and (words := {w for w in map(_normalized, field.suggested_value.split()) if w})
    ]


def _adds_missing(
    change: _WordChange, original: list[str], missing: list[set[str]]
) -> bool:
    """Whether a change also inserts a missing field's value.

    A replacement next to an incorrect field can carry a missing field in with
    it ("WrongVenue." to "CorrectVenue. 2024."), and where a missing field
    goes is a guess.
    """
    replaced = {_normalized(w) for w in original[change.start : change.end]}
    added = {_normalized(w) for w in change.replacement} - replaced
    return any(words <= added for words in missing)


def _unique_quote(
    change: _WordChange,
    original: list[str],
    lines: Sequence[str],
    start_line: int,
    end_line: int,
) -> _Quote | None:
    """The change's words, widened until they appear once on the reference's line."""
    start, end = change.start, change.end
    if not change.replacement or start == end:
        # A deletion takes a neighbouring word with it, so the space before
        # the deleted words goes too; an insertion needs one to quote.
        start, end = (start - 1, end) if start > 0 else (start, end + 1)
    while (
        len(
            find_quote_lines(lines, start_line, end_line, " ".join(original[start:end]))
        )
        != 1
    ):
        if start == 0 and end == len(original):
            return None
        start, end = max(0, start - 1), min(len(original), end + 1)
    return _Quote(start=start, end=end, changes=[change])


def _merged(quotes: list[_Quote]) -> list[_Quote]:
    """Quotes that overlap or touch, joined into one; a superset of a unique quote is unique."""
    merged: list[_Quote] = []
    for quote in sorted(quotes, key=lambda q: q.start):
        if merged and quote.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = _Quote(
                start=last.start,
                end=max(last.end, quote.end),
                changes=[*last.changes, *quote.changes],
            )
        else:
            merged.append(quote)
    return merged


def _edit(
    quote: _Quote,
    original: list[str],
    lines: Sequence[str],
    start_line: int,
    end_line: int,
) -> ProposedEdit | None:
    """The quote with its changes applied, checked against the document's line."""
    words: list[str] = []
    position = quote.start
    for change in sorted(quote.changes, key=lambda c: c.start):
        words += [*original[position : change.start], *change.replacement]
        position = change.end
    words += original[position : quote.end]
    outcome = resolve_edit(
        lines,
        ProposedEditInput(
            original_text=" ".join(original[quote.start : quote.end]),
            replacement_text=" ".join(words),
            # The issue's description already says what is wrong; a rationale
            # would repeat it under every edit.
            rationale="",
        ),
        "edit",
        start_line,
        end_line,
    )
    return outcome if isinstance(outcome, ProposedEdit) else None


def applies_full_correction(
    reference_text: str, updated_reference: str | None, edits: Sequence[ProposedEdit]
) -> bool:
    """Whether applying the edits to the reference gives the validator's correction.

    Then the edits say everything a suggested action would, so the issue can
    leave the action out. Edits whose quotes overlap never pass: the export
    applies only one of them.
    """
    if not edits or not updated_reference:
        return False
    text = " ".join(reference_text.split())
    placed: list[tuple[int, int, str]] = []
    for edit in edits:
        quote = " ".join(edit.original_text.split())
        position = text.find(quote)
        if position < 0:
            return False
        placed.append(
            (position, position + len(quote), " ".join(edit.replacement_text.split()))
        )
    placed.sort()
    if any(a[1] > b[0] for a, b in zip(placed, placed[1:])):
        return False
    pieces, position = [], 0
    for start, end, replacement in placed:
        pieces += [text[position:start], replacement]
        position = end
    pieces.append(text[position:])
    return "".join(pieces) == " ".join(updated_reference.split())
