"""Tests for the abbreviation scan v2 graph nodes, with the agents stubbed."""

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Send

from lib.agents.abbreviation_chunk_extractor import PartialChunkExtractionError
from lib.agents.abbreviations_section_extractor import AbbreviationsSectionExtraction
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    AbbreviationSectionEntry,
    AbbreviationsSectionRange,
    ChunkExtractionResult,
    ChunkOccurrence,
    ChunkStatus,
)
from lib.workflows.abbreviation_scan_v2.graph import build_abbreviation_scan_v2_graph
from lib.workflows.abbreviation_scan_v2.nodes import (
    assemble_catalogue,
    extract_chunks,
    read_abbreviations_section,
)
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationScanV2Config,
    AbbreviationScanV2State,
)
from lib.workflows.models import WorkflowErrorSeverity

MARKDOWN = "# Report\n\nThe NATO alliance.\n\n## Abbreviations\n\n- NATO: North Atlantic Treaty Organization"


def _runtime(markdown: str = MARKDOWN) -> Any:
    service = SimpleNamespace(get_main_file=AsyncMock(return_value=SimpleNamespace(markdown=markdown)))
    return SimpleNamespace(
        context=SimpleNamespace(file_artifacts_service=service, workflow_run_id="run-1", openai_api_key=None)
    )


def _state(**kwargs: Any) -> AbbreviationScanV2State:
    return AbbreviationScanV2State(config=AbbreviationScanV2Config(project_id="p"), **kwargs)


def _chunk(index: int, status: ChunkStatus, occurrences: List[ChunkOccurrence] | None = None) -> AbbreviationChunk:
    return AbbreviationChunk(
        chunk_index=index,
        start_line=1 + index * 3,
        end_line=3 + index * 3,
        status=status,
        occurrences=occurrences or [],
        error=None if status in (ChunkStatus.COMPLETED, ChunkStatus.SKIPPED) else "boom",
    )


def test_graph_compiles():
    build_abbreviation_scan_v2_graph().compile()


class TestDistribute:
    def test_one_send_per_pending_chunk(self):
        state = _state(chunks=[_chunk(0, ChunkStatus.PENDING), _chunk(1, ChunkStatus.SKIPPED), _chunk(2, ChunkStatus.PENDING)])
        sends = extract_chunks.distribute_chunks(state)
        assert isinstance(sends, list)
        assert all(isinstance(s, Send) and s.node == "extract_chunk" for s in sends)
        assert [s.arg["chunk"]["chunk_index"] for s in sends] == [0, 2]

    def test_nothing_pending_goes_straight_to_assembly(self):
        assert extract_chunks.distribute_chunks(_state(chunks=[_chunk(0, ChunkStatus.SKIPPED)])) == "assemble_catalogue"


class TestExtractChunk:
    async def _run(self, agent_result: Any) -> AbbreviationChunk:
        agent = SimpleNamespace(ainvoke=AsyncMock(**agent_result))
        with patch.object(extract_chunks, "AbbreviationChunkExtractorAgent", return_value=agent):
            result = await extract_chunks.extract_chunk_node.__wrapped__(
                {"chunk": _chunk(0, ChunkStatus.PENDING).model_dump(mode="json")}, _runtime()
            )
        self.kwargs = agent.ainvoke.call_args.args[0]
        return result["chunks"][0]

    @pytest.mark.asyncio
    async def test_success_records_occurrences_and_passes_the_document_and_range(self):
        found = ChunkExtractionResult(occurrences=[ChunkOccurrence(abbr="NATO", line_start=3, line_end=3)])
        chunk = await self._run({"return_value": (found, [AIMessage(content="{}")])})
        assert chunk.status == ChunkStatus.COMPLETED
        assert [o.abbr for o in chunk.occurrences] == ["NATO"]
        assert self.kwargs == {"markdown": MARKDOWN, "start_line": 1, "end_line": 3}

    @pytest.mark.asyncio
    async def test_truncation_is_partial_and_keeps_the_salvage(self):
        salvaged = ChunkExtractionResult(occurrences=[ChunkOccurrence(abbr="NATO", line_start=3, line_end=3)])
        chunk = await self._run({"side_effect": PartialChunkExtractionError(salvaged, [])})
        assert chunk.status == ChunkStatus.PARTIAL
        assert len(chunk.occurrences) == 1
        assert chunk.error_details is not None

    @pytest.mark.asyncio
    async def test_failure_is_recorded_on_the_chunk_not_raised(self):
        chunk = await self._run({"side_effect": RuntimeError("rate limited")})
        assert chunk.status == ChunkStatus.ERROR
        assert chunk.error == "rate limited"


class TestAssemble:
    async def _run(self, chunks: List[AbbreviationChunk]) -> dict:
        return await assemble_catalogue.assemble_catalogue_node.__wrapped__(_state(chunks=chunks), _runtime())

    @pytest.mark.asyncio
    async def test_failed_chunks_are_warnings_while_others_produced_results(self):
        result = await self._run(
            [
                _chunk(0, ChunkStatus.COMPLETED, [ChunkOccurrence(abbr="NATO", line_start=3, line_end=3)]),
                _chunk(1, ChunkStatus.ERROR),
                _chunk(2, ChunkStatus.SKIPPED),
            ]
        )
        assert [i.abbr for i in result["abbreviations"]] == ["NATO"]
        [error] = result["errors"]
        assert error.severity == WorkflowErrorSeverity.WARNING
        assert error.chunk_index == 1
        assert "Lines 4-6 could not be scanned" in error.error
        assert "1 failed" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_every_chunk_failing_escalates_to_an_error(self):
        result = await self._run([_chunk(0, ChunkStatus.ERROR), _chunk(1, ChunkStatus.ERROR)])
        assert result["abbreviations"] == []
        assert {e.severity for e in result["errors"]} == {WorkflowErrorSeverity.ERROR}


class TestReadAbbreviationsSection:
    async def _run(self, extraction: AbbreviationsSectionExtraction, markdown: str = MARKDOWN) -> dict:
        conversation = [AIMessage(content="{}")]
        agent = SimpleNamespace(ainvoke=AsyncMock(return_value=(extraction, conversation)))
        with patch.object(read_abbreviations_section, "AbbreviationsSectionExtractorAgent", return_value=agent):
            result = await read_abbreviations_section.read_abbreviations_section_node.__wrapped__(
                _state(), _runtime(markdown)
            )
        assert agent.ainvoke.call_args.args[0] == {"markdown": markdown}
        assert result.get("messages", conversation) == conversation
        return result

    @pytest.mark.asyncio
    async def test_listing_section_is_found_with_its_range_and_entries(self):
        entry = AbbreviationSectionEntry(abbr="NATO", definition="North Atlantic Treaty Organization")
        result = await self._run(
            AbbreviationsSectionExtraction(
                sections=[AbbreviationsSectionRange(start_line=5, end_line=7, lists_abbreviations=True)],
                entries=[entry],
            )
        )
        assert result["abbreviations_section_found"] is True
        assert [(r.start_line, r.end_line) for r in result["abbreviations_section_ranges"]] == [(5, 7)]
        assert result["abbreviations_section_entries"] == [entry]

    @pytest.mark.asyncio
    async def test_glossary_of_ordinary_terms_is_excluded_but_not_found(self):
        result = await self._run(
            AbbreviationsSectionExtraction(
                sections=[AbbreviationsSectionRange(start_line=5, end_line=7, lists_abbreviations=False)]
            )
        )
        assert result["abbreviations_section_found"] is False
        assert [(r.start_line, r.end_line) for r in result["abbreviations_section_ranges"]] == [(5, 7)]

    @pytest.mark.asyncio
    async def test_ranges_are_clamped_to_the_document_and_impossible_ones_dropped(self):
        result = await self._run(
            AbbreviationsSectionExtraction(
                sections=[
                    AbbreviationsSectionRange(start_line=5, end_line=90, lists_abbreviations=True),
                    AbbreviationsSectionRange(start_line=50, end_line=60, lists_abbreviations=True),
                ]
            )
        )
        assert [(r.start_line, r.end_line) for r in result["abbreviations_section_ranges"]] == [(5, 7)]

    @pytest.mark.asyncio
    async def test_no_section(self):
        result = await self._run(AbbreviationsSectionExtraction())
        assert result["abbreviations_section_found"] is False
        assert result["abbreviations_section_ranges"] == []
