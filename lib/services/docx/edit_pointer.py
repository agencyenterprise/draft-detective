"""How a Word comment names a proposed edit in a few words.

An applied edit sits in the text as a tracked change, so the comment does not
quote it again: it points at the words that changed ("build" → "built"), enough
for a reader to match the comment to its redline. An edit that is not in the
text has to be given whole, since the comment is then the only place it is.
"""

import difflib

from lib.services.docx.comment_markup import literal, marked_text, plain_text

# A change of at most this many words on either side is quoted as is.
_SHORT_CHANGE_WORDS = 6
# More separate changes than this read as a rewrite.
_MAX_CHANGES = 2
# Past this share of the sentence's words, the changes read as a rewrite: a word
# diff of a sentence turned around comes out in pieces no reader can follow.
_REWRITE_SHARE = 0.5
# Characters markdown can take as formatting.
_MARKUP_CHARACTERS = "*_`"
# Words quoted from the start of a rewritten sentence.
_LEAD_WORDS = 5


def _quoted(words: list[str]) -> str:
    return f"“{literal(' '.join(words))}”"


def _change(old: list[str], new: list[str]) -> str:
    if not new:
        return f"deletes {_quoted(old)}"
    if not old:
        return f"adds {_quoted(new)}"
    return f"{_quoted(old)} → {_quoted(new)}"


def edit_pointer(original: str, replacement: str) -> str:
    """The changed words of an edit, or the start of the sentence it rewrites."""
    old, new = plain_text(original).split(), plain_text(replacement).split()
    changes = [
        (old[i1:i2], new[j1:j2])
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new).get_opcodes()
        if tag != "equal"
    ]
    short = all(
        len(a) <= _SHORT_CHANGE_WORDS and len(b) <= _SHORT_CHANGE_WORDS
        for a, b in changes
    )
    changed = sum(len(a) for a, _ in changes)
    # A short quote is quoted whole however much of it changes.
    mostly_changed = len(old) > _SHORT_CHANGE_WORDS and changed > _REWRITE_SHARE * len(
        old
    )
    small = short and len(changes) <= _MAX_CHANGES and not mostly_changed
    if changes and small:
        return "; ".join(_change(a, b) for a, b in changes)
    lead = literal(" ".join(old[:_LEAD_WORDS])) + (
        " …" if len(old) > _LEAD_WORDS else ""
    )
    if not new:
        return f"deletes “{lead}”"
    if not changes:
        # Only markup differs, which the quotes leave out.
        return f"reformats “{lead}”"
    return f"rewrites “{lead}”"


def _as_shown(raw: str, shown: str | None) -> str:
    """One side of an edit as the comment quotes it.

    With its own formatting, unless the quote is a fragment of markup that
    reads differently on its own than in the document (the inside of a code
    span, half of a bold phrase): then the text as the document shows it,
    taken literally.
    """
    if shown is not None and _markup_count(plain_text(raw)) != _markup_count(shown):
        return literal(shown)
    return marked_text(raw)


def _markup_count(text: str) -> list[int]:
    """How many of each markup character a text shows.

    A quote parsed on its own that shows fewer than the document does is a
    fragment whose markup the parse took as formatting. Other differences,
    such as a link's destination the comment adds after its label, do not
    count.
    """
    return [text.count(mark) for mark in _MARKUP_CHARACTERS]


def edit_fix(
    original: str,
    replacement: str,
    shown_original: str | None = None,
    shown_replacement: str | None = None,
) -> str:
    """The whole edit, for a comment that is the only place it appears.

    Both sides keep the document's own formatting, which the comment shows as
    such (bold, italics, code as typed), and footnote links read "[N]": a fix
    that differs only in those is still visible, and nothing in it is lost.
    `shown_*` are the sides as the document renders them, for fragments.
    """
    before = _as_shown(original, shown_original)
    if not replacement:
        return f"Delete “{before}”"
    return f"Replace “{before}” with “{_as_shown(replacement, shown_replacement)}”"
