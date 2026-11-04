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


def edit_fix(original: str, replacement: str) -> str:
    """The whole edit, for a comment that is the only place it appears.

    Both sides keep the document's own formatting, which the comment shows as
    such (bold, italics, code as typed), and footnote links read "[N]": a fix
    that differs only in those is still visible, and nothing in it is lost.
    """
    before = marked_text(original)
    if not replacement:
        return f"Delete “{before}”"
    return f"Replace “{before}” with “{marked_text(replacement)}”"
