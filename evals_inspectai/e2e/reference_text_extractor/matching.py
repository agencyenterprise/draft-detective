"""How an extracted reference is compared with an expected one and with the document.

The documents are markdown converted from Word or PDF, so the same entry can
differ in ways that are not the agent's doing: non-breaking spaces, HTML
entities (``&amp;``), markdown escapes (``research\\_reports``), curly quotes,
and a line break that the skill tells the agent to merge, which it may merge
with or without a space (a URL split over two lines). ``normalize`` removes
those; ``compact`` also drops every space, and is what "identical" and
"verbatim" compare.

The skill changes an entry in three ways, and the document checks allow for
each: it removes an entry number or list marker (so the document's lines are
read without one), it merges an entry split across lines (so a reference may
span several lines, but only lines of the same entry: see ``DocumentText``),
and it replaces a repeated-author placeholder (``---.``, ``———.``, ``___``)
with the previous entry's author (so a reference may begin with an author the
document gives only as a placeholder, provided it is that previous author).
"""

import html
import re
from collections import Counter
from typing import Callable, Optional, Sequence

_MD_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
# An entry number or list marker opening a line: "1.", "12)", "[3]", "(4)", "-", "*", "+", "•".
# At most three digits, so a year opening a wrapped line ("2020. Title") is kept.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)]|\[\d{1,3}\]|\(\d{1,3}\))\s+")
# A repeated-author placeholder in compacted text.
_PLACEHOLDER_RE = re.compile(r"-{2,}|—+|–{2,}|_{2,}")
# Word-token Dice coefficient at or above which two references are the same entry.
TOKEN_MATCH = 0.8
# One compacted text inside the other counts as the same entry when the shorter is at
# least this share of the longer: a reference missing its URL, or with a stray suffix.
CONTAINED_SHARE = 0.6


def normalize(text: str) -> str:
    """HTML entities and markdown escapes undone, quotes straightened, whitespace
    (non-breaking spaces included) collapsed to single spaces."""
    text = _MD_ESCAPE_RE.sub(r"\1", html.unescape(text)).translate(_QUOTES)
    return " ".join(text.split())


def compact(text: str) -> str:
    """``normalize`` with every space removed."""
    return "".join(normalize(text).split())


# A paragraph or list item that carries on the previous entry rather than opening one:
# it starts with a URL, a DOI, a lowercase letter, a digit or punctuation (compacted text).
_CONTINUATION_RE = re.compile(r"^(?:https?://|www\.|doi[:.]|[a-z0-9(\[<:;,.)\]/])")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
# How an entry's last line ends when the entry is complete: a full stop, or a closing
# URL, URL remainder (a last token with a slash or a web file extension, as when a URL
# is split over lines) or DOI, since reference styles that end on the link carry no
# final full stop.
_ENDS_ENTRY_RE = re.compile(
    r"(?:[.?!]|(?:https?://|www\.)\S+|\S*/\S*|\S+\.(?:pdf|html?|aspx?|php)|doi:\s*\S+)$", re.I
)


# A year opening the part of an entry after its authors: "2020", "(2020)", "2025a".
_YEAR_RE = re.compile(r"\(?\b(?:1[5-9]|20)\d{2}[a-z]?\b\)?")
# A full stop closing a word of two or more letters (not an initial like "R."), followed by a space.
_NAME_END_RE = re.compile(r"(?<=\w\w)\.(?= )")


class _Entry:
    """One entry of the document as the skill reads it: its normalized text with its
    lines joined by a space (``joins`` holds those spaces' positions, the only places a
    reference may run two lines together without one), which line each stretch comes
    from, and, for an entry opening with a repeated-author placeholder, where the text
    after the placeholder starts and the author it stands for."""

    def __init__(self) -> None:
        self.text = ""
        self.joins: set[int] = set()
        self.pieces: list[tuple[int, int, int]] = []  # (1-indexed line, start, end) in text
        self.last_line = ""  # normalized text of the entry's last line
        self.tail = 0  # for a placeholder entry, where the text after the placeholder starts
        self.authors: tuple[str, ...] = ()  # for a placeholder entry, the spans the previous entry's author may take

    def add(self, number: int, line: str) -> None:
        piece = normalize(line)
        if self.text:
            self.joins.add(len(self.text))
            self.text += " "
        self.pieces.append((number, len(self.text), len(self.text) + len(piece)))
        self.text += piece
        self.last_line = piece

    def lines(self, start: int, end: int) -> tuple[int, int]:
        """The first and last document line holding ``text[start:end]``."""
        covered = [n for n, s, e in self.pieces if s < end and e > start]
        return covered[0], covered[-1]

    def author_spans(self) -> tuple[str, ...]:
        """Where the entry's authors may end, each span without the punctuation and space
        that follow it: before the first year (author-date styles: "Thompson, R. &
        Davis, K. (2022)"), and at the first full stop closing a name rather than an
        initial (notes-bibliography styles: "Marchetti, Lucia. *Title*, 1794")."""
        cuts = [m.start() for m in (_YEAR_RE.search(self.text), _NAME_END_RE.search(self.text)) if m]
        return tuple(dict.fromkeys(span for cut in cuts if (span := self.text[:cut].rstrip(" .,;:"))))


def _align(ref: str, text: str, joins: set[int], start: int) -> Optional[int]:
    """Where ``ref`` ends when it matches ``text`` from ``start``, or None: characters must
    agree, except that a line-join space in ``text`` may be missing from ``ref``, as when
    a URL split over two lines is merged without one. Spaces elsewhere must be kept."""
    i, t = 0, start
    while i < len(ref):
        if t < len(text) and ref[i] == text[t]:
            i, t = i + 1, t + 1
        elif t in joins:
            t += 1
        else:
            return None
    return t


def _continues(entry: _Entry, line: str) -> bool:
    """Whether ``line`` carries on ``entry`` rather than opening the next one: it opens
    like the rest of a reference (a URL, lowercase text, a URL fragment split onto its
    own line), or the entry has not ended (no final full stop, closing URL or DOI), as
    when a line wraps or a conversion splits one reference over two bullets."""
    text = compact(line)
    if _PLACEHOLDER_RE.match(text):
        return False
    fragment = " " not in normalize(line) and "/" in text
    return bool(_CONTINUATION_RE.match(text)) or fragment or not _ENDS_ENTRY_RE.search(entry.last_line)


class DocumentText:
    """A document's lines grouped into entries, so a reference is looked for within one
    entry and never across two. Each line opens an entry unless ``_continues`` says it
    carries on the one above (a wrapped line, a split URL, a reference split over two
    bullets); a heading stands alone."""

    def __init__(self, lines: Sequence[str]) -> None:
        self.entries: list[_Entry] = []
        current: Optional[_Entry] = None
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            heading = bool(_HEADING_RE.match(line))
            body = _LIST_MARKER_RE.sub("", line)
            if heading or current is None or not _continues(current, body):
                current = self._open(body, heading)
            current.add(number, body)
            if heading:
                current = None

    def _open(self, body: str, heading: bool) -> _Entry:
        entry = _Entry()
        placeholder = None if heading else _PLACEHOLDER_RE.match(normalize(body))
        if placeholder:
            entry.tail = placeholder.end()
            source = next((e for e in reversed(self.entries) if e.text and not e.tail), None)
            entry.authors = source.author_spans() if source else ()
        self.entries.append(entry)
        return entry

    def contains(self, reference: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> bool:
        """Whether the reference's text is one entry's text, or part of it, with its spaces
        (see ``_align``); a placeholder entry is read with the placeholder replaced by the
        previous entry's full author, so the reference must start with exactly that
        author. With a line range, only when the matched text lies within those lines."""
        ref = normalize(reference)
        if not ref:
            return False

        def within(entry: _Entry, start: int, end: int) -> bool:
            if start_line is None or end_line is None:
                return True
            first, last = entry.lines(start, end)
            return start_line <= first and last <= end_line

        for entry in self.entries:
            if entry.tail:
                if any(self._resolves(ref, author, entry, within) for author in entry.authors):
                    return True
                continue
            at = entry.text.find(ref[0])
            while at >= 0:
                stop = _align(ref, entry.text, entry.joins, at)
                if stop is not None and within(entry, at, stop):
                    return True
                at = entry.text.find(ref[0], at + 1)
        return False

    @staticmethod
    def _resolves(ref: str, author: str, entry: _Entry, within: Callable[[_Entry, int, int], bool]) -> bool:
        """Whether ``ref`` is ``author`` (one of the previous entry's full author spans)
        followed by the text after this entry's placeholder, from its separating
        punctuation on, so a reference can neither substitute an author of its own nor
        drop co-authors."""
        if not ref.startswith(author):
            return False
        stop = _align(ref[len(author):], entry.text, entry.joins, entry.tail)
        return stop is not None and within(entry, entry.tail, max(stop, entry.tail + 1))


def _tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"\w+", normalize(text).lower()))


def similarity(extracted: str, expected: str) -> Optional[float]:
    """How alike two references are when they are the same entry, else None: 1.0 when
    their compacted texts are identical, otherwise the Dice coefficient of their word
    tokens, raised to ``TOKEN_MATCH`` when one compacted text contains the other and is
    at least ``CONTAINED_SHARE`` of its length."""
    a, b = compact(extracted), compact(expected)
    if a == b:
        return 1.0
    ta, tb = _tokens(extracted), _tokens(expected)
    total = sum(ta.values()) + sum(tb.values())
    dice = 2 * sum((ta & tb).values()) / total if total else 0.0
    short, long = sorted((a, b), key=len)
    if short and short in long and len(short) >= CONTAINED_SHARE * len(long):
        dice = max(dice, TOKEN_MATCH)
    return dice if dice >= TOKEN_MATCH else None


def match(extracted: Sequence[str], expected: Sequence[str]) -> list[tuple[int, int]]:
    """A one-to-one pairing of extracted to expected references, as (extracted index,
    expected index): pairs are taken most-similar first, identical texts before any
    tolerant match, and each reference is used at most once."""
    exact: dict[str, list[int]] = {}
    for j, text in enumerate(expected):
        exact.setdefault(compact(text), []).append(j)
    pairs: list[tuple[int, int]] = []
    left_ext, used_exp = [], set()
    for i, text in enumerate(extracted):
        free = exact.get(compact(text), [])
        if free:
            j = free.pop(0)
            pairs.append((i, j))
            used_exp.add(j)
        else:
            left_ext.append(i)
    left_exp = [j for j in range(len(expected)) if j not in used_exp]
    scored = [
        (sim, i, j)
        for i in left_ext
        for j in left_exp
        if (sim := similarity(extracted[i], expected[j])) is not None
    ]
    taken_ext: set[int] = set()
    taken_exp: set[int] = set()
    for _, i, j in sorted(scored, key=lambda s: -s[0]):
        if i not in taken_ext and j not in taken_exp:
            pairs.append((i, j))
            taken_ext.add(i)
            taken_exp.add(j)
    return pairs
