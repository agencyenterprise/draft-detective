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
from typing import List, Optional

from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from lib.services.text_location import all_offsets
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


def rendered_replacement_in_context(
    line: str, start: int, end: int, replacement: str
) -> Optional[str]:
    """The replacement as the page would show it once it takes the quote's place.

    Rendered *in context*, not on its own, and that is the point. A quote may
    start or end inside formatting that carries on around it: an agent that
    quotes ``old phrase**`` out of ``The **old phrase** matters.`` writes a
    replacement of ``new phrase**``, and the stars are the closing half of the
    document's bold run, not text. Rendered alone that fragment has nothing to
    close, so the stars survive as literals and Word is handed
    ``new phrase**``. Spliced back into the line they close the run they came
    from and disappear, which is what the reader would see.

    It cuts the other way too. ``a*b*c`` inside a code span is literal, so a
    replacement of ``x*y*z`` has to keep its stars -- rendered alone they would
    be read as emphasis and stripped.

    So the replacement goes into the raw line where the quote sat, marked at
    both ends the way `rendered_span` marks the quote, and the whole line is
    rendered. The answer is the characters between the marks, with the
    whitespace the replacement was written with: unlike `display_text` this is
    written into the document verbatim, so a double space between sentences or
    a space separating the replacement from its neighbours is kept. Block
    parsing trims a paragraph's edges, so a replacement that opened or closed
    with whitespace has it put back.

    A quote starting at offset 0 is marked at its end only, for the same
    reason `rendered_span` does it: the line's block syntax has to keep
    working, so ``# Old heading`` -> ``# New heading`` loses its hashes the
    way the heading does rather than writing one into the document as text.

    ``None`` means the replacement cannot be placed there without breaking the
    parse -- it closes a link label and opens a destination that swallows the
    mark, say. There is no text to write in that case, and the edit is
    reported back to the agent rather than guessed at.
    """
    if start < 0 or end > len(line) or start >= end:
        return None
    # A deletion, or whitespace alone: nothing to render, and nothing that
    # could break the formatting around it.
    if not replacement.strip():
        return replacement

    opening = _QUOTE_OPENS if start > 0 else ""
    edited = line[:start] + opening + replacement + _QUOTE_CLOSES + line[end:]
    rendered = render_line_text(edited)

    closes = rendered.find(_QUOTE_CLOSES)
    if closes == -1:
        return None
    if opening:
        opens = rendered.find(_QUOTE_OPENS)
        if opens == -1 or opens > closes:
            return None
        written_from = opens + 1
    else:
        written_from = 0

    written = rendered[written_from:closes].strip()
    leading = replacement[: len(replacement) - len(replacement.lstrip())]
    trailing = replacement[len(replacement.rstrip()) :]
    return leading + written + trailing


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
