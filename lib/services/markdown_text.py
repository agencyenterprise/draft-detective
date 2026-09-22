"""Rendering a markdown line into the characters a reader actually sees.

A proposed edit quotes `original_text` verbatim from the main document's
markdown, so the quote carries syntax nobody reads: `**stress**` is the word
``stress`` on the page and in the DOCX, a link is its label alone, a list
marker is a bullet, and MarkItDown's backslash escapes are literal
punctuation. Anything that wants to find the quote in rendered text -- the
in-app highlight, the DOCX redline -- has to look for the rendered form.

That form is produced once, here, by a real CommonMark parser, and stored on
the edit row when the issue is reported. Nothing downstream re-derives it, so
the highlight and the export cannot drift apart, and neither carries a
hand-written approximation of CommonMark.

Rendering runs through markdown-it, HTML and all: the parser emits HTML, the
tags come off (an image leaves its alt text behind, as the page would show for
a missing picture) and entities are decoded. Typographer and linkify stay off
-- they would rewrite quotes and dashes the document never changed, and turn
bare URLs into links whose label is the URL.

Pure functions only -- no document loading -- so the rules can be unit-tested
on plain strings.
"""

import html
import re
from typing import List, Optional, Tuple

from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from lib.workflows.simple_deep_agent.edit_anchoring import normalize_whitespace

# CommonMark plus the two GFM extensions the converted documents use. No
# typographer and no linkify: both invent text the document does not carry.
_MARKDOWN = MarkdownIt("commonmark").enable("table").enable("strikethrough")

_IMAGE_TAG = re.compile(r"<img\b[^>]*>")
_ALT_ATTRIBUTE = re.compile(r'\balt="([^"]*)"')
_ANY_TAG = re.compile(r"<[^>]*>")

# Where a quote starts and ends in the raw line, carried through the parse so
# the rendered quote can be read back off the rendered line.
#
# Unicode punctuation rather than private-use characters, and that is not a
# detail: CommonMark decides whether `__strong__` is emphasis from what sits
# either side of the delimiters, and a letter-like character next to the
# opening run makes it both left- and right-flanking, which stops an
# underscore run from opening at all. A punctuation character leaves every
# delimiter run deciding exactly as it did without the marks. Both are
# characters no converted document has ever carried.
_QUOTE_OPENS = "⸮"
_QUOTE_CLOSES = "⸘"

# The same class `normalize_whitespace` collapses, one character at a time.
_WHITESPACE = re.compile(r"\s")


class RenderedSpan(BaseModel):
    """Where a quote lands in its line once the line is rendered."""

    display_text: str = Field(
        description="The quote as the document shows it, whitespace-normalized."
    )
    display_occurrence: int = Field(
        description=(
            "0-based index of this occurrence of display_text among the "
            "occurrences the rendered line carries."
        )
    )


def _image_alt(match: "re.Match[str]") -> str:
    """An `<img>` tag reduced to its alt text, which is what a reader is given."""
    alt = _ALT_ATTRIBUTE.search(match.group(0))
    return alt.group(1) if alt else ""


def _text_of(rendered_html: str) -> str:
    """The characters a reader sees in a fragment of rendered HTML."""
    return html.unescape(_ANY_TAG.sub("", _IMAGE_TAG.sub(_image_alt, rendered_html)))


def render_line_text(line: str) -> str:
    """One markdown line as the document shows it, whitespace left as written.

    Block syntax goes with the rest: a heading keeps its words and loses its
    hashes, a list item loses its marker, a blockquote its arrow. Only the
    newlines the renderer wraps a block in are trimmed; whitespace inside the
    line is left alone, so a caller that needs it normalized says so.

    A line that is a table row on its own is not a table -- a GFM table needs
    its delimiter row -- so it renders as the prose it looks like, pipes
    included. That is fine: an edit anchored to a table row is refused before
    its text is ever compared with a paragraph's.
    """
    return _text_of(_MARKDOWN.render(line)).strip("\n")


def render_replacement_text(text: str, *, block_context: bool = False) -> str:
    """An edit's replacement as it should reach the page, whitespace exact.

    A replacement is not a needle: it is written into the document verbatim, so
    every space the edit asked for is kept -- a double space between sentences,
    a non-breaking space inside a figure reference, a leading or trailing space
    that separates the replacement from its neighbours. Only the syntax a
    reader never sees is removed.

    Rendered inline by default, so a leading ``2. `` stays the year or the
    numeral it was written as rather than becoming a list marker: a
    replacement is usually a fragment of a paragraph, never a block of its own.

    `block_context` is for the one case where it is a block: a quote that
    starts at column 0 of its line takes that line's block syntax with it, so
    its replacement was written with the same syntax. ``# Old heading`` ->
    ``# New heading`` is a heading rewritten, and rendering it inline would
    write the hash into the document as text. In block mode the syntax goes
    the way the line's does; only the whitespace the replacement opened or
    closed with is put back, since block parsing trims a paragraph's edges and
    the edit meant those spaces.

    Whether the replacement can be written at all is a separate question, and
    stays with the export (`unsupported_replacement_reason`).
    """
    if not block_context:
        return _text_of(_MARKDOWN.renderInline(text))
    core = text.strip()
    if not core:
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    return leading + _text_of(_MARKDOWN.render(core)).strip("\n") + trailing


def rendered_span(line: str, start: int, end: int) -> Optional[RenderedSpan]:
    """The rendered form of ``line[start:end]``, or None when it has none.

    The raw line is marked at `start` and `end` and rendered with the marks in
    place, so the quote is carried through the same parse as the text around
    it: the answer is exactly the characters the reader sees between those two
    points, however much syntax opened or closed in between.

    ``None`` means the quote cannot be tied to rendered characters -- a mark
    landed inside a link address, an image source or another destination the
    parser consumes, so it never reaches the page. Such a quote has no span to
    highlight and no span to redline, and is reported back to the agent rather
    than guessed at.

    A quote starting at offset 0 is marked at its end only. The opening mark
    would sit in front of the line's block syntax and turn a list item or a
    heading into plain prose, which would hand back a display text carrying the
    bullet the reader never sees; a quote that opens its line opens the
    rendered line too, so its occurrence is 0 by construction.
    """
    if start < 0 or end > len(line) or start >= end:
        return None

    opening = _QUOTE_OPENS if start > 0 else ""
    marked = line[:start] + opening + line[start:end] + _QUOTE_CLOSES + line[end:]
    rendered = normalize_whitespace(render_line_text(marked))

    closes = rendered.find(_QUOTE_CLOSES)
    if closes == -1:
        return None
    # Where the quote's first character sits in the rendered line: after the
    # opening mark, or at the very start when there is none.
    if opening:
        opens = rendered.find(_QUOTE_OPENS)
        if opens == -1 or opens > closes:
            return None
        quote_from = opens + 1
    else:
        opens = 0
        quote_from = 0

    quoted = rendered[quote_from:closes]
    display_text = normalize_whitespace(quoted)
    if not display_text:
        return None

    # Both marks out again, and where the quote starts in what is left: the
    # characters before the opening mark are untouched, so the quote begins
    # where that mark stood, past any whitespace the normalization kept.
    clean = rendered[:opens] + quoted + rendered[closes + 1 :]
    quote_at = opens + (len(quoted) - len(quoted.lstrip()))
    return RenderedSpan(
        display_text=display_text,
        display_occurrence=len(
            [offset for offset in all_offsets(clean, display_text) if offset < quote_at]
        ),
    )


def link_destinations(text: str) -> List[str]:
    """Every markdown link or image destination in `text`, in document order.

    Used to compare a quote with its replacement: Word carries a hyperlink as a
    relationship the paragraph's text does not spell out, so writing the new
    label as a redline would leave the old target in place -- a link saying one
    thing and going somewhere else. An edit that changes a destination is
    reported instead.

    Read off the parser's own inline tokens rather than matched with a regex.
    CommonMark lets a destination hold balanced parentheses, so
    ``[a](https://x/(1))`` points at ``https://x/(1)`` and not at
    ``https://x/(1`` -- and a pattern that stops at the first ``)`` would call
    that destination equal to ``https://x/(2)``'s, which is exactly the
    retarget this check exists to refuse. The parser also knows that
    ``[x](y)`` inside a code span is not a link at all.
    """
    destinations: List[str] = []
    for token in _MARKDOWN.parseInline(text, {}):
        for child in token.children or []:
            attribute = {"link_open": "href", "image": "src"}.get(child.type)
            if attribute is None:
                continue
            # `attrGet` is typed for any attribute value; a destination is a
            # string, and a link the parser built always has one.
            destinations.append(str(child.attrGet(attribute) or ""))
    return destinations


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
