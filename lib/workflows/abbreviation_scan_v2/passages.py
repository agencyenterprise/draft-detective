"""The exact words each abbreviation occurrence's issue is about.

An abbreviation issue concerns a few characters of its line: the abbreviation
used before it was defined, or the definition that disagrees with the
Abbreviations section. Those words are located here, once per occurrence, by
the rule every issue passage follows (`resolve_passage`): verbatim on one line
and unique there. A definition is located as written ("Full Name (ABBR)", then
the name alone); a bare abbreviation is located as the token the line carries,
widened a word at a time until it is unique, since an abbreviation often
repeats on its line. An occurrence none of these pin down has no passage and
its issue concerns the whole line, as before.
"""

import re
from collections.abc import Iterator, Sequence

from lib.workflows.abbreviation_scan_v2.catalogue import abbreviation_pattern
from lib.workflows.abbreviation_scan_v2.state import AbbreviationItem
from lib.workflows.models import LocatedQuote
from lib.workflows.simple_deep_agent.issue_reporting import resolve_passage

# How many words a repeated abbreviation is widened by before giving up.
_MAX_WIDENING = 6
_WORD = re.compile(r"\S+")


def _token_span(line: str, abbr: str, nth: int) -> tuple[int, int] | None:
    """Where the `nth` (0-based) whole-token `abbr` sits on the line."""
    pattern = abbreviation_pattern(abbr)
    if pattern is None:
        return None
    matches = list(pattern.finditer(line))
    if nth >= len(matches):
        return None
    start, end = matches[nth].span()
    # A dotted spelling ends on its own dot ("U.S."), which the pattern leaves
    # out because a bare "US" has none.
    if "." in line[start:end] and line[end : end + 1] == ".":
        end += 1
    return start, end


def _widened(line: str, start: int, end: int) -> Iterator[str]:
    """The token, its whole word, then one more word each side, left first.

    Widening goes by whole words, so a token inside punctuation ("CAIRNE)")
    grows to the word that carries it before taking a neighbour, and a passage
    never ends halfway through a word. The word before goes first: it is
    usually what the abbreviation names ("renamed CAIRNE"), where the word
    after is often only "which" or "and".
    """
    yield line[start:end]
    words = [match.span() for match in _WORD.finditer(line)]
    start = min([s for s, e in words if s <= start < e] or [start])
    end = max([e for s, e in words if s < end <= e] or [end])
    yield _trimmed(line[start:end])
    before = [span for span in words if span[1] <= start]
    after = [span for span in words if span[0] >= end]
    for step in range(_MAX_WIDENING):
        if step % 2 == 0 and before:
            start = before.pop()[0]
        elif after:
            end = after.pop(0)[1]
        elif before:
            start = before.pop()[0]
        else:
            return
        yield _trimmed(line[start:end])


def _trimmed(word: str) -> str:
    """A word without the punctuation at its edges that it does not close.

    "CAIRNE)" out of "(Lab, now CAIRNE)" keeps no bracket it never opened,
    and a word ending a clause sheds its comma.
    """
    word = word.rstrip(",;:")
    if word.endswith(")") and "(" not in word:
        word = word[:-1]
    if word.startswith("(") and ")" not in word:
        word = word[1:]
    return word


def _candidates(item: AbbreviationItem, line: str, nth: int) -> Iterator[str]:
    span = _token_span(line, item.abbr, nth)
    token = line[span[0] : span[1]] if span else item.abbr
    if item.inline_definition:
        yield f"{item.inline_definition} ({token})"
        yield item.inline_definition
    if span:
        yield from _widened(line, *span)


def occurrence_passage(
    lines: Sequence[str], item: AbbreviationItem, nth_on_line: int
) -> LocatedQuote | None:
    """The occurrence's words as a located passage, or None for its whole line.

    `nth_on_line` is which of the abbreviation's tokens on the line this
    occurrence is, counted in reading order.
    """
    if not 1 <= item.line_start <= len(lines):
        return None
    line = lines[item.line_start - 1]
    for quote in _candidates(item, line, nth_on_line):
        located = resolve_passage(lines, quote, item.line_start, item.line_start)
        if isinstance(located, LocatedQuote):
            return located
    return None


def with_passages(
    lines: Sequence[str], catalogue: list[AbbreviationItem]
) -> list[AbbreviationItem]:
    """The catalogue with each occurrence's passage located."""
    seen: dict[tuple[str, int], int] = {}
    located: list[AbbreviationItem] = []
    for item in catalogue:
        key = (item.abbr, item.line_start)
        nth = seen.get(key, 0)
        seen[key] = nth + 1
        passage = occurrence_passage(lines, item, nth)
        located.append(item.model_copy(update={"passage": passage}))
    return located
