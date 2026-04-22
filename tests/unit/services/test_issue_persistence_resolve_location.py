"""Tests for issue_persistence._resolve_location."""

from pydantic import BaseModel

from lib.services.issue_persistence import _resolve_location
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType


class FakeChunk(BaseModel):
    chunk_index: int
    start_line: int
    end_line: int


def _chunks() -> list[FakeChunk]:
    return [
        FakeChunk(chunk_index=0, start_line=1, end_line=10),
        FakeChunk(chunk_index=1, start_line=11, end_line=20),
        FakeChunk(chunk_index=2, start_line=21, end_line=30),
    ]


def _issue(**overrides) -> DocumentIssue:
    base = dict(
        title="t",
        description="d",
        severity=SeverityEnum.LOW,
        type=WorkflowRunType.CLAIM_EXTRACTION,
    )
    base.update(overrides)
    return DocumentIssue(**base)


class TestResolveLocation:
    def test_line_range_only_derives_chunk_indices(self):
        issue = _issue(start_line=5, end_line=15)
        chunk_indices, start_line, end_line = _resolve_location(issue, _chunks())
        assert chunk_indices == [0, 1]
        assert start_line == 5
        assert end_line == 15

    def test_chunk_indices_only_derives_line_range(self):
        issue = _issue(chunk_indices=[1, 2])
        chunk_indices, start_line, end_line = _resolve_location(issue, _chunks())
        assert chunk_indices == [1, 2]
        assert start_line == 11
        assert end_line == 30

    def test_both_set_passes_through(self):
        issue = _issue(chunk_indices=[0], start_line=99, end_line=100)
        chunk_indices, start_line, end_line = _resolve_location(issue, _chunks())
        assert chunk_indices == [0]
        assert start_line == 99
        assert end_line == 100

    def test_neither_set_returns_none(self):
        issue = _issue()
        chunk_indices, start_line, end_line = _resolve_location(issue, _chunks())
        assert chunk_indices is None
        assert start_line is None
        assert end_line is None

    def test_no_chunks_passes_through_what_we_have(self):
        issue = _issue(start_line=5, end_line=15)
        chunk_indices, start_line, end_line = _resolve_location(issue, None)
        assert chunk_indices is None
        assert start_line == 5
        assert end_line == 15

    def test_line_range_with_no_overlap_yields_none_chunk_indices(self):
        issue = _issue(start_line=100, end_line=200)
        chunk_indices, start_line, end_line = _resolve_location(issue, _chunks())
        assert chunk_indices is None
        assert start_line == 100
        assert end_line == 200
