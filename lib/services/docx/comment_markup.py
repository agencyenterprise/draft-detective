"""Issue text as a Word comment can show it.

Issues are written in markdown, which a Word comment would show raw: asterisks
round bold words, backticks, `### headings` and footnote links such as
`[[100]](#footnote-101)`. A comment's text keeps just two marks, `**bold**` and
`*italic*`, and `write_comment` turns each line into a paragraph of the comment
with those spans formatted.
"""

import re

from docx.comments import Comment
from docx.text.paragraph import Paragraph

_FOOTNOTE_LINK = re.compile(r"\[\[\d+\]\]\(#footnote-\d+\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.M)
_HEADING_MARK = re.compile(r"^#{1,6}\s+", re.M)
# `**bold**` (group 1) or `*italic*` (group 2); a lone asterisk, as in a
# "* item" bullet or "5 * 3", is left alone.
_SPAN = re.compile(r"\*\*(.+?)\*\*|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def comment_markdown(text: str) -> str:
    """Issue markdown reduced to what a comment shows: bold, italic and lines."""
    text = _FOOTNOTE_LINK.sub("", text)
    text = _HEADING.sub(r"**\1**", text)
    return text.replace("`", "")


def plain_text(text: str) -> str:
    """Document text with no marks at all, for quoting it inside a comment."""
    text = _HEADING_MARK.sub("", _FOOTNOTE_LINK.sub("", text)).replace("`", "")
    return _SPAN.sub(lambda m: m.group(1) or m.group(2), text)


def _write_line(paragraph: Paragraph, line: str) -> None:
    position = 0
    for match in _SPAN.finditer(line):
        if match.start() > position:
            paragraph.add_run(line[position : match.start()])
        run = paragraph.add_run(match.group(1) or match.group(2))
        if match.group(1):
            run.bold = True
        else:
            run.italic = True
        position = match.end()
    if position < len(line):
        paragraph.add_run(line[position:])


def write_comment(comment: Comment, text: str) -> None:
    """Fill an empty comment with `text`, one paragraph per line."""
    first, *rest = text.split("\n")
    # The first paragraph already holds the run with the comment's reference
    # mark (`w:annotationRef`), which every Word comment carries; the text
    # follows it.
    _write_line(comment.paragraphs[0], first)
    for line in rest:
        _write_line(comment.add_paragraph(), line)
