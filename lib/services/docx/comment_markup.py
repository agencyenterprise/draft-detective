"""Issue text as a Word comment can show it.

Issues are written in markdown, which a Word comment would show raw: asterisks
round bold words, backticks, `### headings` and footnote links such as
`[[100]](#footnote-101)`. A comment's text keeps `**bold**`, `*italic*` (also
nested, and `***both***`) and `` `code` ``, whose content is shown literally;
`write_comment` turns each line into a paragraph of the comment with those spans
formatted and the marks themselves dropped.
"""

import re

from docx.comments import Comment
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

_FOOTNOTE_LINK = re.compile(r"\[\[(\d+)\]\]\(#footnote-\d+\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.M)
_HEADING_MARK = re.compile(r"^#{1,6}\s+", re.M)
# One span, in the order tried at each position: inline code (1), bold italic
# (2), bold (3) or italic (4). A lone asterisk, as in a "* item" bullet or
# "5 * 3", is left alone.
_SPAN = re.compile(
    r"`([^`\n]+)`"
    r"|\*\*\*(?!\s)(.+?)(?<!\s)\*\*\*"
    r"|\*\*(?!\s)(.+?)(?<!\s)\*\*"
    r"|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"
)


class Segment(BaseModel):
    """A stretch of comment text with one formatting."""

    text: str
    bold: bool = False
    italic: bool = False


def segments(text: str, bold: bool = False, italic: bool = False) -> list[Segment]:
    """`text` split into formatted stretches, its marks dropped.

    Bold and italic nest (`**a *term* here**`); code is taken literally, so
    asterisks inside it stay text.
    """
    out: list[Segment] = []
    position = 0
    for match in _SPAN.finditer(text):
        if match.start() > position:
            out.append(
                Segment(text=text[position : match.start()], bold=bold, italic=italic)
            )
        code, both, strong, emphasis = match.groups()
        if code is not None:
            out.append(Segment(text=code, bold=bold, italic=italic))
        elif both is not None:
            out += segments(both, True, True)
        elif strong is not None:
            out += segments(strong, True, italic)
        else:
            out += segments(emphasis, bold, True)
        position = match.end()
    if position < len(text):
        out.append(Segment(text=text[position:], bold=bold, italic=italic))
    return out


def comment_markdown(text: str) -> str:
    """Issue markdown reduced to what a comment shows: emphasis, code and lines."""
    text = _FOOTNOTE_LINK.sub("", text)
    # A heading's own bold marks would nest inside the bold it becomes.
    return _HEADING.sub(lambda m: f"**{m[1].replace('**', '')}**", text)


def footnote_labels(text: str) -> list[str]:
    """The footnote numbers a text's footnote links show, in order."""
    return _FOOTNOTE_LINK.findall(text)


def literal(text: str) -> str:
    """`text` marked so that the comment shows it as is.

    Quoted document text has lost its own marks, so any asterisk left in it is
    literal; inline code keeps it from being read as emphasis again.
    """
    return f"`{text}`" if "*" in text and "`" not in text else text


def marked_text(text: str) -> str:
    """Document text with its emphasis kept and footnote links as "[N]".

    For quoting an edit whose only change is in what `plain_text` drops.
    """
    return _HEADING_MARK.sub("", _FOOTNOTE_LINK.sub(r"[\1]", text))


def plain_text(text: str) -> str:
    """Document text with no marks at all, for quoting it inside a comment."""
    text = _HEADING_MARK.sub("", _FOOTNOTE_LINK.sub("", text))
    return "".join(segment.text for segment in segments(text))


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
