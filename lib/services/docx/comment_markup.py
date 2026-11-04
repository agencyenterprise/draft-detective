"""Issue text as a Word comment can show it.

Issues are written in markdown, which a Word comment would show raw: asterisks
round bold words, backticks, `### headings` and footnote links such as
`[[100]](#footnote-101)`. A comment's text is a line-by-line CommonMark
subset: `**bold**`, `*italic*` (nested as markdown allows), `` `code` `` shown
literally and backslash escapes; `write_comment` turns each line into a
paragraph of the comment with those spans formatted and the marks dropped.
"""

import re

from docx.comments import Comment
from docx.text.paragraph import Paragraph
from markdown_it import MarkdownIt
from pydantic import BaseModel

_FOOTNOTE_LINK = re.compile(r"\[\[(\d+)\]\]\(#footnote-\d+\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.M)
_HEADING_MARK = re.compile(r"^#{1,6}\s+", re.M)
# A code fence: three or more backticks or tildes.
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
# CommonMark inline parsing, as the documents' own markdown is read elsewhere
# (`lib.services.text.markdown_rendering`): nesting, shared closing delimiters,
# code spans and backslash escapes behave as markdown defines them.
_INLINE = MarkdownIt("commonmark")
# Characters that can start inline markup in CommonMark (emphasis, code, links,
# HTML, entities, escapes); a backslash before one keeps it literal.
_INLINE_MARKUP = re.compile(r"([\\`*_\[\]<>&])")
# Tokens whose content is shown as text; any other token is a mark.
_TEXT_TOKENS = {"text", "code_inline"}
_HTML_TAG = re.compile(r"^<(/?)([A-Za-z][\w-]*)")
# HTML tags read as the markdown emphasis they stand for.
_HTML_EMPHASIS = {"em": "em", "i": "em", "b": "strong", "strong": "strong"}
# HTML tags dropped, keeping what they enclose: formatting a comment cannot
# show, and tags models leak into issue text (`<cite index="…">` from search
# results, `<parameter name="…">` from tool calls). Any other tag-like text,
# such as a `<name>` placeholder, is kept as written.
_HTML_DROPPED = {
    "a",
    "br",
    "cite",
    "div",
    "font",
    "mark",
    "p",
    "parameter",
    "small",
    "span",
    "sub",
    "sup",
    "u",
}


class Segment(BaseModel):
    """A stretch of comment text with one formatting."""

    text: str
    bold: bool = False
    italic: bool = False


def segments(text: str) -> list[Segment]:
    """One line of markdown split into formatted stretches, its marks dropped.

    Bold and italic nest (`**a *term* here**`); code is taken literally, so
    asterisks inside it stay text. A link keeps its destination after its
    label, since a comment cannot link (see `_link_target`), and an image
    becomes its alt text and source.
    """
    if not text:
        return []
    (line,) = _INLINE.parseInline(text)
    out: list[Segment] = []
    bold = italic = 0
    links: list[tuple[str, int]] = []
    for token in line.children or []:
        kind = _kind(token.type, token.content)
        if kind == "html_break":
            out.append(Segment(text=" ", bold=bold > 0, italic=italic > 0))
        elif kind == "link_open":
            links.append((str(token.attrs.get("href", "")), len(out)))
        elif kind == "link_close" and links:
            href, start = links.pop()
            label = "".join(segment.text for segment in out[start:])
            if target := _link_target(href, label):
                out.append(Segment(text=target, bold=bold > 0, italic=italic > 0))
        elif kind == "image":
            # An image reads like a link: its alt text as rendered, then its
            # source.
            alt = "".join(
                c.content for c in token.children or [] if c.type in _TEXT_TOKENS
            )
            src = str(token.attrs.get("src", ""))
            image = alt + (_link_target(src, alt) or "")
            out.append(Segment(text=image, bold=bold > 0, italic=italic > 0))
        elif kind == "strong_open":
            bold += 1
        elif kind == "strong_close":
            bold -= 1
        elif kind == "em_open":
            italic += 1
        elif kind == "em_close":
            italic -= 1
        elif kind in _TEXT_TOKENS and token.content:
            out.append(Segment(text=token.content, bold=bold > 0, italic=italic > 0))
    return out


def _kind(token_type: str, content: str) -> str:
    """A token's type, with inline HTML read as the markdown it stands for.

    An emphasis tag becomes `em_open`, `strong_close` and so on; a dropped tag
    becomes `html_dropped` (`html_break` for `<br>`, which keeps a space); any
    other tag-like text is plain `text`.
    """
    if token_type != "html_inline":
        return token_type
    match = _HTML_TAG.match(content)
    if match is None:
        return "text"
    closing, name = match[1], match[2].lower()
    if name in _HTML_EMPHASIS:
        return f"{_HTML_EMPHASIS[name]}_{'close' if closing else 'open'}"
    if name == "br":
        return "html_break"
    return "html_dropped" if name in _HTML_DROPPED else "text"


def _link_target(href: str, label: str) -> str | None:
    """What follows a link's label in a comment, or None for nothing.

    The destination, in parentheses, unless it is the label itself or a
    footnote link, whose number the label already shows.
    """
    if not href or href.startswith("#footnote-") or href == label:
        return None
    return f" ({href})"


def literal(text: str) -> str:
    """`text` escaped so that the comment shows it exactly as it is."""
    return _INLINE_MARKUP.sub(r"\\\1", text)


def _fenced(lines: list[str]) -> list[bool | None]:
    """For each line: None for a code fence, True inside a fenced block.

    A block closes only on a bare fence of its opener's character, at least as
    long, so a fence shown inside the block (``` inside ````, or "```python")
    stays code.
    """
    opener: str | None = None
    kinds: list[bool | None] = []
    for line in lines:
        match = _FENCE.match(line)
        fence = match[1] if match else None
        bare = match is not None and not match[2].strip()
        if fence and opener is None:
            opener = fence
            kinds.append(None)
        elif (
            fence
            and opener
            and bare
            and fence[0] == opener[0]
            and len(fence) >= len(opener)
        ):
            opener = None
            kinds.append(None)
        else:
            kinds.append(opener is not None)
    return kinds


def comment_markdown(text: str) -> str:
    """Issue markdown reduced to what a comment shows: emphasis, code and lines.

    Fenced code blocks are left as they are, for `write_comment` to show
    literally.
    """
    lines = text.split("\n")
    return "\n".join(
        line if kind is not False else _comment_line(line)
        for line, kind in zip(lines, _fenced(lines), strict=True)
    )


def _comment_line(line: str) -> str:
    line = _FOOTNOTE_LINK.sub("", line)
    # A heading's own bold marks would nest inside the bold it becomes.
    return _HEADING.sub(lambda m: f"**{m[1].replace('**', '')}**", line)


def marked_text(text: str) -> str:
    """Document text with its emphasis kept and footnote links as "[N]".

    For quoting a proposed edit in full, formatting and footnotes included.
    """
    return _HEADING_MARK.sub("", _FOOTNOTE_LINK.sub(r"[\1]", text))


def plain_text(text: str) -> str:
    """Document text with no marks at all, for quoting it inside a comment."""
    text = _HEADING_MARK.sub("", _FOOTNOTE_LINK.sub("", text))
    return "\n".join(
        "".join(segment.text for segment in segments(line)) for line in text.split("\n")
    )


def _write_line(paragraph: Paragraph, line: str) -> None:
    for segment in segments(line):
        run = paragraph.add_run(segment.text)
        if segment.bold:
            run.bold = True
        if segment.italic:
            run.italic = True


def write_comment(comment: Comment, text: str) -> None:
    """Fill an empty comment with `text`, one paragraph per line.

    The lines of a fenced code block are written as they are, without the
    fences.
    """
    lines = text.split("\n")
    # The first paragraph already holds the run with the comment's reference
    # mark (`w:annotationRef`), which every Word comment carries; the text
    # follows it.
    paragraph: Paragraph | None = comment.paragraphs[0]
    for line, kind in zip(lines, _fenced(lines), strict=True):
        if kind is None:
            continue
        paragraph = paragraph or comment.add_paragraph()
        if kind:
            paragraph.add_run(line)
        else:
            _write_line(paragraph, line)
        paragraph = None
