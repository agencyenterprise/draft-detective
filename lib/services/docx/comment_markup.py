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
# CommonMark inline parsing, as the documents' own markdown is read elsewhere
# (`lib.services.text.markdown_rendering`): nesting, shared closing delimiters,
# code spans and backslash escapes behave as markdown defines them.
_INLINE = MarkdownIt("commonmark")
# Characters that can start inline markup in CommonMark (emphasis, code, links,
# HTML, entities, escapes); a backslash before one keeps it literal.
_INLINE_MARKUP = re.compile(r"([\\`*_\[\]<>&])")
# Tokens whose content is shown as text; any other token is a mark.
_TEXT_TOKENS = {"text", "code_inline", "html_inline"}


class Segment(BaseModel):
    """A stretch of comment text with one formatting."""

    text: str
    bold: bool = False
    italic: bool = False


def segments(text: str) -> list[Segment]:
    """One line of markdown split into formatted stretches, its marks dropped.

    Bold and italic nest (`**a *term* here**`); code is taken literally, so
    asterisks inside it stay text. A link keeps its destination after its
    label, since a comment cannot link: see `_link_target`.
    """
    if not text:
        return []
    (line,) = _INLINE.parseInline(text)
    out: list[Segment] = []
    bold = italic = 0
    links: list[tuple[str, int]] = []
    for token in line.children or []:
        if token.type == "link_open":
            links.append((str(token.attrs.get("href", "")), len(out)))
        elif token.type == "link_close" and links:
            href, start = links.pop()
            label = "".join(segment.text for segment in out[start:])
            if target := _link_target(href, label):
                out.append(Segment(text=target, bold=bold > 0, italic=italic > 0))
        elif token.type == "strong_open":
            bold += 1
        elif token.type == "strong_close":
            bold -= 1
        elif token.type == "em_open":
            italic += 1
        elif token.type == "em_close":
            italic -= 1
        elif token.type in _TEXT_TOKENS and token.content:
            out.append(Segment(text=token.content, bold=bold > 0, italic=italic > 0))
    return out


def _link_target(href: str, label: str) -> str | None:
    """What follows a link's label in a comment, or None for nothing.

    The destination, in parentheses, unless it is the label itself or an
    anchor inside the document (a footnote link).
    """
    if not href or href.startswith("#") or href == label:
        return None
    return f" ({href})"


def literal(text: str) -> str:
    """`text` escaped so that the comment shows it exactly as it is."""
    return _INLINE_MARKUP.sub(r"\\\1", text)


def comment_markdown(text: str) -> str:
    """Issue markdown reduced to what a comment shows: emphasis, code and lines."""
    text = _FOOTNOTE_LINK.sub("", text)
    # A heading's own bold marks would nest inside the bold it becomes.
    return _HEADING.sub(lambda m: f"**{m[1].replace('**', '')}**", text)


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
    """Fill an empty comment with `text`, one paragraph per line."""
    first, *rest = text.split("\n")
    # The first paragraph already holds the run with the comment's reference
    # mark (`w:annotationRef`), which every Word comment carries; the text
    # follows it.
    _write_line(comment.paragraphs[0], first)
    for line in rest:
        _write_line(comment.add_paragraph(), line)
