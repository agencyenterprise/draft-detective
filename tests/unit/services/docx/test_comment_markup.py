"""Tests for turning issue markdown into a Word comment's formatting."""

from docx import Document

from lib.services.docx.comment_markup import (
    comment_markdown,
    literal,
    plain_text,
    segments,
    write_comment,
)


def test_markdown_a_comment_cannot_show_is_reduced():
    text = "### Field validations\nUse `decisionmaking`.[[100]](#footnote-101)"

    assert comment_markdown(text) == "**Field validations**\nUse `decisionmaking`."
    assert (
        plain_text(comment_markdown(text)) == "Field validations\nUse decisionmaking."
    )


def test_a_bold_heading_is_not_bolded_twice():
    assert comment_markdown("### **Note** here") == "**Note here**"


def test_a_literal_quote_is_shown_as_is():
    assert [(s.text, s.bold) for s in segments(literal("a**b**c"))] == [
        ("a**b**c", False)
    ]


def test_nested_emphasis_is_formatted_without_stray_marks():
    assert [
        (s.text, s.bold, s.italic) for s in segments("***both*** and **a *term* here**")
    ] == [
        ("both", True, True),
        (" and ", False, False),
        ("a ", True, False),
        ("term", True, True),
        (" here", True, False),
    ]


def test_bold_and_italic_can_close_together():
    assert [(s.text, s.bold, s.italic) for s in segments("**bold *and italic***")] == [
        ("bold ", True, False),
        ("and italic", True, True),
    ]


def test_a_link_keeps_its_destination():
    text = "see [NeurIPS](https://x/a), <https://y.org> and [1](#footnote-2)"
    assert "".join(s.text for s in segments(text)) == (
        "see NeurIPS (https://x/a), https://y.org and 1"
    )


def test_an_image_reads_as_its_alt_text_and_source():
    text = "see ![Figure 1](files/fig.png) here"
    assert (
        "".join(s.text for s in segments(text)) == "see Figure 1 (files/fig.png) here"
    )


def test_an_image_alt_text_is_read_as_rendered():
    assert "".join(s.text for s in segments("![**Figure** 1](a.png)")) == (
        "Figure 1 (a.png)"
    )


def test_code_is_quoted_literally():
    assert [(s.text, s.bold) for s in segments("Keep `**name**` literally")] == [
        ("Keep ", False),
        ("**name**", False),
        (" literally", False),
    ]


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


def test_a_fenced_block_is_written_literally_without_its_fences():
    document = Document()
    paragraph = document.add_paragraph("anchor")
    comment = document.add_comment(
        runs=paragraph.runs, text="", author="DD", initials="DD"
    )
    text = comment_markdown("**Title**\n```\na*b*c and ### not a heading\n```\nafter")

    write_comment(comment, text)

    assert [p.text for p in comment.paragraphs] == [
        "Title",
        "a*b*c and ### not a heading",
        "after",
    ]


def test_an_anchor_that_is_not_a_footnote_keeps_its_target():
    assert "".join(s.text for s in segments("[Methods](#methods-1)")) == (
        "Methods (#methods-1)"
    )


def test_a_literal_url_keeps_its_underscores():
    url = "https://dd.example/share/_abcd_-1234#lines-3-4"
    assert "".join(s.text for s in segments(literal(url))) == url


def test_html_tags_render_or_drop_and_placeholders_stay():
    text = 'a <em>warning</em>,<br>see (<cite index="38-1">Smith</cite>) for <name>'
    assert [(s.text, s.italic) for s in segments(text) if s.text.strip()] == [
        ("a ", False),
        ("warning", True),
        (",", False),
        ("see (", False),
        ("Smith", False),
        (") for ", False),
        ("<name>", False),
    ]


def test_a_fence_closes_only_on_a_matching_fence():
    document = Document()
    paragraph = document.add_paragraph("anchor")
    comment = document.add_comment(
        runs=paragraph.runs, text="", author="DD", initials="DD"
    )
    text = "**Title**\n````\n```\n**kept**\n```\n````\nafter"

    write_comment(comment, comment_markdown(text))

    assert [p.text for p in comment.paragraphs] == [
        "Title",
        "```",
        "**kept**",
        "```",
        "after",
    ]


def test_a_fence_with_an_info_string_inside_a_block_is_content():
    document = Document()
    paragraph = document.add_paragraph("anchor")
    comment = document.add_comment(
        runs=paragraph.runs, text="", author="DD", initials="DD"
    )
    text = "**Title**\n```\n```python\n**kept**\n```\nafter"

    write_comment(comment, comment_markdown(text))

    assert [p.text for p in comment.paragraphs] == [
        "Title",
        "```python",
        "**kept**",
        "after",
    ]
