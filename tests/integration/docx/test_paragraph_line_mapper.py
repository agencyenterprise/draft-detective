"""Tests for the docx paragraph → markdown line-range mapper."""

from pathlib import Path

import pytest
from docx import Document

from lib.services.converters.markitdown import markitdown_converter
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
