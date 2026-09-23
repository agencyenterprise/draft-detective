"""Tests for abbreviation scan v2 chunking."""

from lib.workflows.abbreviation_scan_v2.chunk_models import ChunkStatus, LineRange
from lib.workflows.abbreviation_scan_v2.layout import CHUNK_CHARS, build_chunks, is_heading_line

DOC = """\
# Machine Learning in Drug Discovery

## Abbreviations

- ML: Machine Learning
- FDA: Food and Drug Administration

## Introduction

Machine Learning (ML) is accelerating drug discovery.

## References

- Smith (2022). ML Methods.
- Jones (2023). FDA Frameworks."""

SECTION = [LineRange(start_line=3, end_line=7)]


def test_chunks_cover_every_line_contiguously():
    chunks = build_chunks(DOC, SECTION)
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == len(DOC.split("\n"))
    for before, after in zip(chunks, chunks[1:]):
        assert after.start_line == before.end_line + 1


def test_the_abbreviations_section_gets_its_own_skipped_chunk():
    chunks = build_chunks(DOC, SECTION)
    assert [(c.start_line, c.end_line, c.status, c.skip_reason) for c in chunks] == [
        (1, 2, ChunkStatus.PENDING, None),
        (3, 7, ChunkStatus.SKIPPED, "abbreviations section"),
        (8, 15, ChunkStatus.PENDING, None),
    ]


def test_without_a_section_a_short_document_is_one_chunk():
    assert [(c.start_line, c.end_line) for c in build_chunks(DOC, [])] == [(1, 15)]


def test_long_documents_are_packed_under_the_budget():
    paragraph = "The NATO alliance met again. " * 20
    doc = "\n\n".join(f"## Section {i}\n\n{paragraph}" for i in range(60))
    chunks = build_chunks(doc, [])
    lines = doc.split("\n")
    sizes = [sum(len(line) + 1 for line in lines[c.start_line - 1 : c.end_line]) for c in chunks]
    assert 1 < len(chunks) < 60
    assert max(sizes) <= CHUNK_CHARS


def test_blank_chunks_are_skipped_and_empty_documents_yield_nothing():
    assert build_chunks("   \n\n", []) == []
    chunks = build_chunks("\n\n\n" + "x" * CHUNK_CHARS + "\n# Title\nText", [])
    assert (chunks[0].status, chunks[0].skip_reason) == (ChunkStatus.SKIPPED, "blank")


def test_heading_lines():
    assert is_heading_line("## Introduction")
    assert not is_heading_line("#hashtag")
    assert not is_heading_line("Text with # inside")
