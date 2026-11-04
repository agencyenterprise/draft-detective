"""Tests for turning issue markdown into a Word comment's formatting."""

from docx import Document

from lib.services.docx.comment_markup import (
    comment_markdown,
    plain_text,
    write_comment,
)


def test_markdown_a_comment_cannot_show_is_reduced():
    text = "### Field validations\nUse `decisionmaking`.[[100]](#footnote-101)"

    assert comment_markdown(text) == "**Field validations**\nUse decisionmaking."


def test_plain_text_drops_every_mark():
    assert plain_text("the **Five Forces** *model* `x`") == "the Five Forces model x"


def test_a_quoted_heading_loses_its_marker():
    assert plain_text("#### Concept 5: Develop") == "Concept 5: Develop"


def test_a_lone_asterisk_is_not_emphasis():
    assert plain_text("* item and 5 * 3") == "* item and 5 * 3"


def test_each_line_becomes_a_paragraph_with_bold_and_italic_runs():
    document = Document()
    paragraph = document.add_paragraph("anchor")
    comment = document.add_comment(
        runs=paragraph.runs, text="", author="DD", initials="DD"
    )

    write_comment(comment, "**Title** · Check\nA *term* here.")

    first, second = comment.paragraphs
    # The first run holds the comment's reference mark and no text.
    assert [(run.text, run.bold) for run in first.runs if run.text] == [
        ("Title", True),
        (" · Check", None),
    ]
    assert [(run.text, run.italic) for run in second.runs] == [
        ("A ", None),
        ("term", True),
        (" here.", None),
    ]


def test_the_comment_keeps_its_annotation_reference():
    # Word writes every comment with a run holding <w:annotationRef/>; it has no
    # text, and the written lines must follow it rather than replace it.
    document = Document()
    paragraph = document.add_paragraph("anchor")
    comment = document.add_comment(
        runs=paragraph.runs, text="", author="DD", initials="DD"
    )

    write_comment(comment, "**Title** · Check")

    assert "annotationRef" in comment._comment_elm.xml
