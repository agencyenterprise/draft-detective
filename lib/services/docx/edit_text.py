"""Turning a markdown quote into the text a Word paragraph actually carries.

A proposed edit quotes `original_text` verbatim from the main document's
markdown, so the quote can carry syntax the reader never sees: `**stress**` is
the word ``stress`` in the DOCX, a link is its label alone, and MarkItDown's
backslash escapes are literal punctuation. Searching a Word paragraph for the
raw quote would therefore fail on exactly the passages an edit is most likely
to touch, so the syntax is stripped down to the characters that reach the page.

The rules are a port of the frontend's `edit-highlight.ts`, which paints the
same quote on the rendered document. Keeping the two in step matters: an author
who sees a span highlighted in the app should get that span redlined in the
export. HTML entities are deliberately not decoded on either side.

Pure functions only -- no document loading -- so the rules can be unit-tested
on plain strings.
"""

import re
from typing import List, Optional, Sequence, Tuple

from lib.workflows.simple_deep_agent.edit_anchoring import normalize_whitespace

# A link label may itself hold one level of brackets: MarkItDown writes a DOCX
# footnote reference as `[[1]](#footnote-2)`, which the document shows as `[1]`.
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\([^)]*\)")
_IMAGE = re.compile(r"!\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\([^)]*\)")
_CODE_FENCE = re.compile(r"`+")
_STRIKETHROUGH = re.compile(r"~~")
_STARS = re.compile(r"\*{1,3}")
# Only underscores standing outside a word: `snake_case` is a name in the text,
# not emphasis, and stripping its underscores would stop it matching.
_UNDERSCORE_OPEN = re.compile(r"(^|[^A-Za-z0-9])_{1,3}")
_UNDERSCORE_CLOSE = re.compile(r"_{1,3}($|[^A-Za-z0-9])")
_BLOCK_PREFIX = re.compile(r"^[ \t]*(?:#{1,6}|>+)[ \t]*", re.MULTILINE)
_LIST_MARKER = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+", re.MULTILINE)

# Backslash-escaped punctuation, as CommonMark defines it: the document shows
# the character itself, so `foo\_bar` in the source reads `foo_bar` on the page.
_ESCAPED_PUNCTUATION = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")

# Private-use code points stand in for escaped characters while syntax is
# stripped, so `\*` survives the emphasis pass as an asterisk.
_PLACEHOLDER_BASE = 0xE000
_PLACEHOLDER_RANGE = re.compile(r"[\uE000-\uE0FF]")

# Marks where the quote starts in the source while the syntax around it is
# stripped. Outside the escape placeholders' range on purpose.
_QUOTE_MARK = "\ue1ff"

# The same class `normalize_whitespace` collapses, one character at a time.
_WHITESPACE = re.compile(r"\s")


def _protect_escaped(text: str) -> str:
    return _ESCAPED_PUNCTUATION.sub(
        lambda m: chr(_PLACEHOLDER_BASE + ord(m.group(1))), text
    )


def _restore_escaped(text: str) -> str:
    return _PLACEHOLDER_RANGE.sub(
        lambda m: chr(ord(m.group(0)) - _PLACEHOLDER_BASE), text
    )


def strip_markdown(text: str) -> str:
    """Drop the markdown syntax a reader never sees from a quote."""
    stripped = _protect_escaped(text)
    stripped = _IMAGE.sub(r"\1", stripped)
    stripped = _LINK.sub(r"\1", stripped)
    stripped = _CODE_FENCE.sub("", stripped)
    stripped = _STRIKETHROUGH.sub("", stripped)
    stripped = _STARS.sub("", stripped)
    stripped = _UNDERSCORE_OPEN.sub(r"\1", stripped)
    stripped = _UNDERSCORE_CLOSE.sub(r"\1", stripped)
    stripped = _BLOCK_PREFIX.sub("", stripped)
    stripped = _LIST_MARKER.sub("", stripped)
    return _restore_escaped(stripped)


def word_search_text(original_text: str) -> str:
    """What to look for in a Word paragraph, given an edit's raw markdown quote."""
    return normalize_whitespace(strip_markdown(original_text))


def all_offsets(haystack: str, needle: str) -> List[int]:
    """Start offset of every occurrence of `needle`, overlapping ones included."""
    offsets: List[int] = []
    if not needle:
        return offsets
    position = haystack.find(needle)
    while position != -1:
        offsets.append(position)
        position = haystack.find(needle, position + 1)
    return offsets


def _normalized_index(text: str) -> Tuple[str, List[int]]:
    """Whitespace-normalize `text`, keeping each character's source offset.

    Mirrors the frontend's `buildTextIndex`: a run of whitespace collapses to
    one space, a leading run to nothing, and the space is emitted just before
    the character that ended the run -- so both share that character's offset.
    The mapping is what lets a normalized match be handed back as the exact
    substring of the original, non-breaking spaces and all.
    """
    normalized: List[str] = []
    sources: List[int] = []
    pending_space = False
    for offset, char in enumerate(text):
        if _WHITESPACE.match(char):
            pending_space = bool(normalized)
            continue
        if pending_space:
            normalized.append(" ")
            sources.append(offset)
            pending_space = False
        normalized.append(char)
        sources.append(offset)
    return "".join(normalized), sources


def locate_in_paragraph(paragraph_text: str, needle: str) -> List[Tuple[int, int]]:
    """Every occurrence of `needle` in `paragraph_text`, as original-text spans.

    `needle` is matched on a whitespace-normalized basis (the paragraph and the
    quote drift at the character level: non-breaking spaces inside prose,
    double spaces before footnote markers), but each returned ``[start, end)``
    indexes `paragraph_text` itself, so ``paragraph_text[start:end]`` is the
    exact substring to search the document for.

    Matching is case-sensitive: the export writes a redline, so a span that
    only matches once the case is ignored is left for a human to place.
    """
    if not needle:
        return []
    normalized, sources = _normalized_index(paragraph_text)
    spans: List[Tuple[int, int]] = []
    for offset in all_offsets(normalized, needle):
        spans.append((sources[offset], sources[offset + len(needle) - 1] + 1))
    return spans


def source_occurrence(
    source_lines: Sequence[str],
    block_start: int,
    block_end: int,
    start_line: int,
    original_text: str,
) -> Optional[int]:
    """Which occurrence of the stripped quote an edit means, or None.

    `original_text` is unique on its own line as written, but stripping the
    syntax can create duplicates: `**Figure 3**` is a unique quote in
    ``Figure 3 and **Figure 3**`` and the paragraph carries ``Figure 3``
    twice. The block's source lines are stripped the same way the quote is,
    with a marker at the quote's position, so counting the stripped quote
    before the marker says which occurrence the edit was anchored to.

    `block_start`/`block_end` are the 1-indexed markdown lines the target Word
    paragraph covers; `start_line` is the edit's own line.
    """
    if start_line < 1 or start_line > len(source_lines):
        return None
    normalized_line = normalize_whitespace(source_lines[start_line - 1])
    quote_at = all_offsets(normalized_line, normalize_whitespace(original_text))
    if len(quote_at) != 1:
        return None

    marked = (
        normalized_line[: quote_at[0]] + _QUOTE_MARK + normalized_line[quote_at[0] :]
    )
    first = max(1, block_start)
    last = min(len(source_lines), block_end)
    stripped = [
        word_search_text(marked if number == start_line else source_lines[number - 1])
        for number in range(first, last + 1)
    ]
    haystack = " ".join(stripped)
    mark_at = haystack.find(_QUOTE_MARK)
    if mark_at == -1:
        return None
    # The marker sits where the stripped quote starts, so the occurrences that
    # begin before it are exactly the ones the paragraph carries ahead of it.
    clean = haystack.replace(_QUOTE_MARK, "")
    needle = word_search_text(original_text)
    return len([offset for offset in all_offsets(clean, needle) if offset < mark_at])
