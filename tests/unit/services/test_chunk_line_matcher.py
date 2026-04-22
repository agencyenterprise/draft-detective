"""Tests for chunk line matcher utilities."""

import pytest

from pydantic import BaseModel

from lib.services.chunk_line_matcher import (
    find_chunk_by_fuzzy_match,
    find_chunk_by_line,
    find_chunks_by_fuzzy_match,
    find_chunks_by_line_range,
    find_line_range_by_chunks,
)


class FakeChunk(BaseModel):
    chunk_index: int
    start_line: int
    end_line: int


class FakeChunkWithContent(BaseModel):
    chunk_index: int
    start_line: int
    end_line: int
    content: str


def _make_chunks() -> list[FakeChunk]:
    return [
        FakeChunk(chunk_index=0, start_line=1, end_line=10),
        FakeChunk(chunk_index=1, start_line=11, end_line=20),
        FakeChunk(chunk_index=2, start_line=21, end_line=30),
        FakeChunk(chunk_index=3, start_line=31, end_line=40),
    ]


class TestFindChunksByLineRange:
    def test_exact_match_single_chunk(self):
        chunks = _make_chunks()
        assert find_chunks_by_line_range(chunks, 1, 10) == [0]

    def test_range_spanning_two_chunks(self):
        chunks = _make_chunks()
        assert find_chunks_by_line_range(chunks, 5, 15) == [0, 1]

    def test_range_spanning_all_chunks(self):
        chunks = _make_chunks()
        assert find_chunks_by_line_range(chunks, 1, 40) == [0, 1, 2, 3]

    def test_single_line_at_boundary(self):
        chunks = _make_chunks()
        assert find_chunks_by_line_range(chunks, 10, 10) == [0]
        assert find_chunks_by_line_range(chunks, 11, 11) == [1]

    def test_no_overlap(self):
        chunks = _make_chunks()
        assert find_chunks_by_line_range(chunks, 50, 60) == []

    def test_empty_chunks(self):
        assert find_chunks_by_line_range([], 1, 10) == []

    def test_results_are_sorted(self):
        chunks = [
            FakeChunk(chunk_index=5, start_line=1, end_line=10),
            FakeChunk(chunk_index=2, start_line=11, end_line=20),
        ]
        assert find_chunks_by_line_range(chunks, 1, 20) == [2, 5]


class TestFindChunkByLine:
    def test_line_in_first_chunk(self):
        chunks = _make_chunks()
        assert find_chunk_by_line(chunks, 5) == 0

    def test_line_in_last_chunk(self):
        chunks = _make_chunks()
        assert find_chunk_by_line(chunks, 35) == 3

    def test_line_at_chunk_start(self):
        chunks = _make_chunks()
        assert find_chunk_by_line(chunks, 21) == 2

    def test_line_at_chunk_end(self):
        chunks = _make_chunks()
        assert find_chunk_by_line(chunks, 20) == 1

    def test_line_not_found(self):
        chunks = _make_chunks()
        assert find_chunk_by_line(chunks, 100) is None

    def test_empty_chunks(self):
        assert find_chunk_by_line([], 1) is None

    def test_returns_first_match_for_overlapping_chunks(self):
        chunks = [
            FakeChunk(chunk_index=0, start_line=1, end_line=15),
            FakeChunk(chunk_index=1, start_line=10, end_line=20),
        ]
        assert find_chunk_by_line(chunks, 12) == 0


class TestFindChunkByFuzzyMatch:
    def test_exact_match(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0, start_line=1, end_line=10, content="The quick brown fox"
            ),
            FakeChunkWithContent(
                chunk_index=1, start_line=11, end_line=20, content="Lazy dog sleeps"
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "The quick brown fox") == 0

    def test_partial_match(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="The quick brown fox jumped over the lazy dog",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="A completely different sentence about cats",
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "brown fox jumped") == 0

    def test_empty_input_text(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0, start_line=1, end_line=10, content="Some content"
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "") is None
        assert find_chunk_by_fuzzy_match(chunks, "   ") is None

    def test_empty_chunks(self):
        assert find_chunk_by_fuzzy_match([], "some text") is None

    def test_chunks_with_empty_content_are_skipped(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0, start_line=1, end_line=10, content=""
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="The answer is here",
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "The answer is here") == 1

    def test_tie_break_by_start_line(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="repeated phrase in document",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=50,
                end_line=60,
                content="repeated phrase in document",
            ),
        ]
        result = find_chunk_by_fuzzy_match(
            chunks, "repeated phrase in document", start_line=48
        )
        assert result == 1

    def test_tie_break_by_chunk_index_without_start_line(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="same text here",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="same text here",
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "same text here") == 0

    def test_below_cutoff_still_returns_match(self):
        """score_cutoff returns 0 for low scores, which still beats initial -1.0."""
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="completely unrelated content about quantum physics",
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "xyz") == 0

    def test_all_empty_content_returns_none(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0, start_line=1, end_line=10, content=""
            ),
            FakeChunkWithContent(
                chunk_index=1, start_line=11, end_line=20, content=""
            ),
        ]
        assert find_chunk_by_fuzzy_match(chunks, "some text") is None

    def test_end_line_filters_to_matching_range(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="target phrase here",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="target phrase here",
            ),
            FakeChunkWithContent(
                chunk_index=2,
                start_line=21,
                end_line=30,
                content="something else entirely",
            ),
        ]
        result = find_chunk_by_fuzzy_match(
            chunks, "target phrase here", start_line=11, end_line=20
        )
        assert result == 1

    def test_end_line_range_spans_multiple_chunks(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="unrelated content about weather",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="the best matching text is here",
            ),
            FakeChunkWithContent(
                chunk_index=2,
                start_line=21,
                end_line=30,
                content="also some matching text nearby",
            ),
        ]
        result = find_chunk_by_fuzzy_match(
            chunks, "the best matching text is here", start_line=10, end_line=25
        )
        assert result == 1

    def test_end_line_no_overlapping_chunks_returns_none(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="target phrase",
            ),
        ]
        result = find_chunk_by_fuzzy_match(
            chunks, "target phrase", start_line=50, end_line=60
        )
        assert result is None

    def test_start_line_without_end_line_still_only_tie_breaks(self):
        """start_line alone does not filter — preserves backward compat."""
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="same text",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=100,
                end_line=110,
                content="same text",
            ),
        ]
        result = find_chunk_by_fuzzy_match(
            chunks, "same text", start_line=105
        )
        assert result == 1


class TestFindChunksByFuzzyMatch:
    def test_single_sentence_matches_one_chunk(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="The economy grew by 5% last year.",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="Inflation remained stable at 2%.",
            ),
        ]
        result = find_chunks_by_fuzzy_match(chunks, "The economy grew by 5% last year.")
        assert result == [0]

    def test_multi_sentence_matches_multiple_chunks(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="The economy grew by 5% last year.",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="Inflation remained stable at 2%.",
            ),
        ]
        result = find_chunks_by_fuzzy_match(
            chunks,
            "The economy grew by 5% last year. Inflation remained stable at 2%.",
        )
        assert 0 in result
        assert 1 in result

    def test_empty_input(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0, start_line=1, end_line=10, content="content"
            ),
        ]
        assert find_chunks_by_fuzzy_match(chunks, "") == []
        assert find_chunks_by_fuzzy_match(chunks, "   ") == []

    def test_empty_chunks(self):
        assert find_chunks_by_fuzzy_match([], "some text") == []

    def test_results_are_deduplicated_and_sorted(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="First sentence here. Second sentence here.",
            ),
        ]
        result = find_chunks_by_fuzzy_match(
            chunks, "First sentence here. Second sentence here."
        )
        assert result == [0]

    def test_end_line_restricts_search_range(self):
        chunks = [
            FakeChunkWithContent(
                chunk_index=0,
                start_line=1,
                end_line=10,
                content="The economy grew by 5% last year.",
            ),
            FakeChunkWithContent(
                chunk_index=1,
                start_line=11,
                end_line=20,
                content="Inflation remained stable at 2%.",
            ),
            FakeChunkWithContent(
                chunk_index=2,
                start_line=21,
                end_line=30,
                content="Unemployment dropped sharply.",
            ),
        ]
        result = find_chunks_by_fuzzy_match(
            chunks,
            "The economy grew by 5% last year. Inflation remained stable at 2%.",
            start_line=1,
            end_line=15,
        )
        assert 0 in result
        assert 1 in result
        assert 2 not in result


class TestFindLineRangeByChunks:
    def test_single_chunk(self):
        chunks = _make_chunks()
        assert find_line_range_by_chunks(chunks, [1]) == (11, 20)

    def test_contiguous_chunks(self):
        chunks = _make_chunks()
        assert find_line_range_by_chunks(chunks, [1, 2]) == (11, 30)

    def test_non_contiguous_chunks_collapses_gaps(self):
        chunks = _make_chunks()
        # Gap between chunks 0 and 2 is collapsed into the spanning range.
        assert find_line_range_by_chunks(chunks, [0, 2]) == (1, 30)

    def test_missing_index_returns_partial_range(self):
        chunks = _make_chunks()
        # 99 doesn't exist; the range uses the remaining matches.
        assert find_line_range_by_chunks(chunks, [0, 99]) == (1, 10)

    def test_all_missing(self):
        chunks = _make_chunks()
        assert find_line_range_by_chunks(chunks, [99]) is None

    def test_empty_indices(self):
        chunks = _make_chunks()
        assert find_line_range_by_chunks(chunks, []) is None

    def test_empty_chunks(self):
        assert find_line_range_by_chunks([], [0]) is None
