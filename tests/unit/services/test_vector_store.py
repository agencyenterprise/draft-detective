"""Unit tests for vector_store chunking and line-range computation."""

import pytest

from lib.services.vector_store import (
    _char_offset_to_line,
    _splitter,
    build_chunk_docs,
)


def _build_doc_with_repeated_sections() -> str:
    """Build a test document where the same block appears in two sections.

    The repeated block is large enough (>800 chars) to be split into
    multiple chunks by the splitter, which is essential for triggering
    the duplicate-text bug that this test suite guards against.
    """
    repeated_lines = [
        f"Repeated claim sentence number {i} that provides "
        "important evidence about the research findings."
        for i in range(12)
    ]
    repeated_block = "\n".join(repeated_lines)

    unique_lines = [
        f"Unique filler sentence {i} in the middle section "
        "describing different methodology."
        for i in range(12)
    ]
    unique_block = "\n".join(unique_lines)

    return (
        f"# Section 1\n\n{repeated_block}\n\n"
        f"# Section 2\n\n{unique_block}\n\n"
        f"# Section 3\n\n{repeated_block}\n\n"
        f"# Section 4\n\nFinal conclusion paragraph.\n"
    )


class TestCharOffsetToLine:
    """Tests for _char_offset_to_line helper."""

    def test_first_char_is_line_one(self):
        assert _char_offset_to_line("hello\nworld", 0) == 1

    def test_second_line(self):
        assert _char_offset_to_line("hello\nworld", 6) == 2

    def test_newline_char_belongs_to_current_line(self):
        assert _char_offset_to_line("hello\nworld", 5) == 1


class TestBuildChunkDocs:
    """Tests for build_chunk_docs which splits text and computes line ranges."""

    def test_simple_document(self):
        """A small document should produce a single chunk with correct range."""
        text = "line 1\nline 2\nline 3"
        docs = build_chunk_docs(text, "test.md", "col_1")

        assert len(docs) >= 1
        first = docs[0]
        assert first.metadata["start_line"] == 1
        assert first.metadata["end_line"] == 3

    def test_duplicate_sections_content_matches_line_range(self):
        """Each chunk's content must exactly match the document lines at its
        computed [start_line, end_line] range.

        This is the strongest regression test for the duplicate-text bug:
        the old str.find() approach mapped later repeated chunks to the
        *first* occurrence's line numbers.  A first/last-line text check
        alone wouldn't catch this (the text is identical at both positions),
        but reconstructing from the line range and comparing full content does.
        """
        doc = _build_doc_with_repeated_sections()
        doc_lines = doc.split("\n")
        docs = build_chunk_docs(doc, "test.md", "col_1")

        for i, chunk_doc in enumerate(docs):
            start = chunk_doc.metadata["start_line"]
            end = chunk_doc.metadata["end_line"]

            reconstructed = "\n".join(doc_lines[start - 1 : end])
            assert reconstructed == chunk_doc.page_content, (
                f"Chunk {i}: content at lines {start}-{end} does not match "
                f"chunk text.\n"
                f"  Reconstructed: {reconstructed[:120]!r}...\n"
                f"  Chunk content: {chunk_doc.page_content[:120]!r}..."
            )

    def test_chunk_line_ranges_are_monotonically_non_decreasing(self):
        """Chunk start_lines should never go backwards (they form a
        monotonically non-decreasing sequence, allowing overlap)."""
        doc = _build_doc_with_repeated_sections()
        docs = build_chunk_docs(doc, "test.md", "col_1")

        prev_start = 0
        for i, chunk_doc in enumerate(docs):
            start = chunk_doc.metadata["start_line"]
            assert start >= prev_start, (
                f"Chunk {i} starts at line {start} which is before "
                f"previous chunk's start at line {prev_start}"
            )
            prev_start = start

    def test_end_line_is_gte_start_line(self):
        """end_line must be >= start_line for every chunk."""
        doc = _build_doc_with_repeated_sections()
        docs = build_chunk_docs(doc, "test.md", "col_1")

        for i, chunk_doc in enumerate(docs):
            start = chunk_doc.metadata["start_line"]
            end = chunk_doc.metadata["end_line"]
            assert (
                end >= start
            ), f"Chunk {i}: end_line {end} is less than start_line {start}"

    def test_metadata_includes_file_name_and_collection(self):
        """Verify that file_name and collection_id are set in metadata."""
        docs = build_chunk_docs("some text", "report.pdf", "col_abc")

        assert len(docs) >= 1
        assert docs[0].metadata["file_name"] == "report.pdf"
        assert docs[0].metadata["collection_id"] == "col_abc"
