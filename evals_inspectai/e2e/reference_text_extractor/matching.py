"""How an extracted reference is compared with an expected one and with the document.

The documents are markdown converted from Word or PDF, so the same entry can
differ in ways that are not the agent's doing: non-breaking spaces, HTML
entities (``&amp;``), markdown escapes (``research\\_reports``), curly quotes,
and a line break that the skill tells the agent to merge, which it may merge
with or without a space (a URL split over two lines). ``normalize`` removes
those; ``compact`` also drops every space, and is what "identical" and
"verbatim" compare.

The skill changes an entry in two ways, and the document checks allow for
both: it removes an entry number or list marker (so the document's lines are
read without one), and it replaces a repeated-author placeholder (``---.``,
``———.``, ``___``) with the previous entry's author (so a reference may begin
with an author the document gives only as a placeholder).
"""

import html
import re
from collections import Counter
from typing import Optional, Sequence

_MD_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
# An entry number or list marker opening a line: "1.", "12)", "[3]", "(4)", "-", "*", "+", "•".
# At most three digits, so a year opening a wrapped line ("2020. Title") is kept.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)]|\[\d{1,3}\]|\(\d{1,3}\))\s+")
# A repeated-author placeholder in compacted text.
_PLACEHOLDER_RE = re.compile(r"-{2,}|—+|–{2,}|_{2,}")
# The shortest tail that must follow a placeholder for a reference to count as that entry.
_MIN_TAIL = 15

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


def haystack(lines: Sequence[str]) -> str:
    """Document lines as one compacted string, each line without a leading list marker."""
    return "".join(compact(_LIST_MARKER_RE.sub("", line)) for line in lines)


def _after_placeholder(ref: str, hay: str) -> bool:
    """Whether ``ref`` is some author followed by text that follows a placeholder in ``hay``."""
    for match in _PLACEHOLDER_RE.finditer(hay):
        start = match.end()
        if start >= len(hay):
            continue
        for k in range(1, len(ref) - _MIN_TAIL + 1):
            if ref[k] == hay[start] and hay.startswith(ref[k:], start):
                return True
    return False


def appears_in(reference: str, hay: str) -> bool:
    """Whether the reference's text is in ``hay`` (a ``haystack``), directly or after a
    repeated-author placeholder the reference has resolved."""
    ref = compact(reference)
    return bool(ref) and (ref in hay or _after_placeholder(ref, hay))


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
