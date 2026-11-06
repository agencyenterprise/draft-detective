"""Tests for the docx paragraph → markdown line-range mapper."""

import copy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from PIL import Image

from lib.services.converters.markitdown import markitdown_converter
from lib.services.docx.drawing_rasterization import (
    CHART_GRAPHIC_URI,
    rasterize_docx_drawings,
    stub_docx_drawings,
)
from lib.services.docx.manipulator import (
    CommentSeverity,
    DocxComment,
    DocxManipulatorService,
)
from lib.services.docx.paragraph_line_mapper import (
    build_paragraph_line_ranges,
    find_paragraph_by_line_range,
)
from tests.conftest import (
    create_test_file_document_from_path,
    data_path,
    write_docx_with_equations,
)


@pytest.mark.asyncio
async def test_build_paragraph_line_ranges_maps_every_non_empty_paragraph():
    """Every non-empty body paragraph gets an entry whose start line sits within
    the original markdown's line count."""
    docx_path = data_path("evals/data/geopolitics-of-agi-minimal-1/_original.docx")
    doc = Document(docx_path)
    non_empty = [p for p in doc.paragraphs if p.text.strip()]
    original_md = await markitdown_converter.convert_to_markdown(str(docx_path))
    total_lines = original_md.count("\n") + 1

    ranges = await build_paragraph_line_ranges(str(docx_path))

    assert len(ranges) == len(non_empty)
    for i, (start, end) in ranges.items():
        assert 0 <= i < len(non_empty)
        assert 1 <= start <= end <= total_lines


@pytest.mark.asyncio
async def test_build_paragraph_line_ranges_start_lines_are_monotonic():
    """Marker injection preserves document order: paragraph N's start line should
    be <= paragraph N+1's start line (equality only when they share a markdown
    line, e.g. table cells)."""
    docx_path = data_path("evals/data/geopolitics-of-agi-minimal-1/_original.docx")
    ranges = await build_paragraph_line_ranges(str(docx_path))

    previous_start = 0
    for _, (start, _end) in sorted(ranges.items(), key=lambda kv: kv[0]):
        assert start >= previous_start
        previous_start = start


def test_find_paragraph_by_line_range_overlap_and_miss():
    mapping = {0: (1, 5), 2: (6, 10), 5: (11, 20)}
    assert find_paragraph_by_line_range(mapping, 3, 4) == 0
    assert find_paragraph_by_line_range(mapping, 5, 7) == 0  # boundary overlap
    assert find_paragraph_by_line_range(mapping, 12, 15) == 5
    assert find_paragraph_by_line_range(mapping, 100, 200) is None


def test_find_paragraph_by_line_range_tie_breaks_to_lowest_index():
    mapping = {4: (5, 15), 1: (5, 15)}
    assert find_paragraph_by_line_range(mapping, 5, 15) == 1


@pytest.mark.asyncio
async def test_add_comments_to_docx_end_to_end():
    """Comments resolve to concrete docx paragraphs via the new mapper."""
    file_doc = await create_test_file_document_from_path(
        "evals/data/geopolitics-of-agi-minimal-1/_original.docx"
    )

    ranges = await build_paragraph_line_ranges(file_doc.file_path)
    mapped_paragraphs = sorted(ranges.keys())
    assert len(mapped_paragraphs) >= 3

    comments = [
        DocxComment(
            paragraph_index=mapped_paragraphs[0],
            comment_text="High priority issue found",
            severity=CommentSeverity.HIGH,
        ),
        DocxComment(
            paragraph_index=mapped_paragraphs[1],
            comment_text="Medium priority suggestion",
            severity=CommentSeverity.MEDIUM,
        ),
        DocxComment(
            paragraph_index=mapped_paragraphs[2],
            comment_text="Low priority note",
            severity=CommentSeverity.LOW,
        ),
    ]
    assert comments[0].get_initials() == "HP"
    assert comments[1].get_initials() == "MP"
    assert comments[2].get_initials() == "LP"

    service = DocxManipulatorService()
    output_path = await service.add_comments_to_docx(
        original_docx_path=file_doc.file_path,
        comments=comments,
        workflow_run_id="test-run-paragraph-line-mapper",
    )
    assert Path(output_path).exists()
    assert len(Document(output_path).paragraphs) > 0


@pytest.mark.asyncio
async def test_document_with_no_text_paragraphs_maps_to_nothing(tmp_path):
    path = str(tmp_path / "empty.docx")
    Document().save(path)

    assert await build_paragraph_line_ranges(path) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_equations", [True, False])
async def test_build_paragraph_line_ranges_matches_markdown_with_or_without_equations(
    tmp_path: Path, keep_equations: bool
):
    """Markdown stored before equations were kept dropped them all; the mapper
    still anchors against it, and against markdown converted today."""
    docx_path = write_docx_with_equations(tmp_path / "equations.docx")
    persisted = await markitdown_converter.convert_to_markdown(
        docx_path, keep_equations=keep_equations
    )
    persisted_lines = persisted.splitlines()

    ranges = await build_paragraph_line_ranges(
        docx_path, expected_line_count=persisted.count("\n") + 1
    )

    paragraphs = [p.text for p in Document(docx_path).paragraphs if p.text.strip()]
    assert len(ranges) == len(paragraphs)
    for i, (start, _end) in ranges.items():
        assert persisted_lines[start - 1].startswith(paragraphs[i].split()[0])


def _chart_paragraph():
    return parse_xml(
        f"<w:p {nsdecls('w', 'wp', 'a', 'r', 'c')}><w:r><w:drawing><wp:inline>"
        '<wp:extent cx="914400" cy="457200"/>'
        f'<a:graphic><a:graphicData uri="{CHART_GRAPHIC_URI}">'
        '<c:chart r:id="rId999"/></a:graphicData></a:graphic>'
        "</wp:inline></w:drawing></w:r></w:p>"
    )


def _write_docx_with_charts(path: Path) -> str:
    document = Document()
    chart = _chart_paragraph()
    for i in range(3):
        document.add_paragraph(f"Paragraph {i} before chart {i}.")
        document.element.body.get_or_add_sectPr().addprevious(copy.deepcopy(chart))
    document.add_paragraph("Closing paragraph.")
    document.save(str(path))
    return str(path)


async def _markdown_with_rendered_charts(docx_path: str, tmp_path: Path) -> str:
    """The markdown ingestion stores when LibreOffice rendered the charts."""
    renders = []
    for i in range(3):
        render = tmp_path / f"render-{i}.png"
        Image.new("RGB", (20, 10), "navy").save(render, format="PNG")
        renders.append(str(render))
    render_dir = tmp_path / "render-dir"
    render_dir.mkdir()
    with patch(
        "lib.services.docx.drawing_rasterization._render_drawings_to_images",
        new=AsyncMock(return_value=(str(render_dir), renders)),
    ):
        rasterized = await rasterize_docx_drawings(docx_path)
    assert rasterized is not None
    try:
        return await markitdown_converter.convert_to_markdown(rasterized)
    finally:
        Path(rasterized).unlink()


@pytest.mark.asyncio
@pytest.mark.parametrize("charts_rendered_at_ingestion", [True, False])
async def test_build_paragraph_line_ranges_with_charts_never_renders_them(
    tmp_path: Path, charts_rendered_at_ingestion: bool
):
    """Charts take markdown lines only when ingestion rendered them. The mapper
    anchors against either markdown, and never starts LibreOffice to do so."""
    docx_path = _write_docx_with_charts(tmp_path / "charts.docx")
    if charts_rendered_at_ingestion:
        persisted = await _markdown_with_rendered_charts(docx_path, tmp_path)
    else:
        persisted = await markitdown_converter.convert_to_markdown(docx_path)
    persisted_lines = persisted.splitlines()

    with patch(
        "lib.services.docx.drawing_rasterization._render_drawings_to_images"
    ) as render_mock:
        ranges = await build_paragraph_line_ranges(
            docx_path, expected_line_count=persisted.count("\n") + 1
        )

    render_mock.assert_not_called()
    paragraphs = [p.text for p in Document(docx_path).paragraphs if p.text.strip()]
    assert len(ranges) == len(paragraphs)
    for i, (start, _end) in ranges.items():
        assert persisted_lines[start - 1] == paragraphs[i]


@pytest.mark.asyncio
async def test_build_paragraph_line_ranges_converts_once_when_charts_were_rendered(
    tmp_path: Path,
):
    """The usual export, charts rendered at ingestion, costs one conversion."""
    docx_path = _write_docx_with_charts(tmp_path / "charts.docx")
    persisted = await _markdown_with_rendered_charts(docx_path, tmp_path)

    with patch.object(
        markitdown_converter,
        "convert_to_markdown",
        wraps=markitdown_converter.convert_to_markdown,
    ) as convert:
        ranges = await build_paragraph_line_ranges(
            docx_path, expected_line_count=persisted.count("\n") + 1
        )

    assert ranges
    assert convert.call_count == 1


@pytest.mark.asyncio
async def test_build_paragraph_line_ranges_refuses_a_chart_and_equation_tie(
    tmp_path: Path,
):
    """Stubbed charts with equations dropped can come to the same line count
    as equations kept without charts, while placing paragraphs differently.
    The mapper must not anchor against either."""
    docx_path = write_docx_with_equations(tmp_path / "mixed.docx")
    document = Document(docx_path)
    document.paragraphs[0]._element.addprevious(_chart_paragraph())
    document.save(docx_path)
    # Stored as when ingestion could not render the chart but kept equations.
    persisted = await markitdown_converter.convert_to_markdown(docx_path)
    stub = stub_docx_drawings(docx_path)
    assert stub is not None
    try:
        tie = await markitdown_converter.convert_to_markdown(stub, keep_equations=False)
    finally:
        Path(stub).unlink()
    assert tie.count("\n") == persisted.count("\n")  # the tie under test

    ranges = await build_paragraph_line_ranges(
        docx_path, expected_line_count=persisted.count("\n") + 1
    )

    assert ranges == {}
