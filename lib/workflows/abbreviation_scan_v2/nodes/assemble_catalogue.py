"""Combine chunk extractions into the catalogue for abbreviation scan v2."""

import logging
from typing import List

from langgraph.runtime import Runtime

from lib.workflows.abbreviation_scan_v2.catalogue import assemble_catalogue
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    ChunkStatus,
)
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationItem,
    AbbreviationScanV2State,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError, WorkflowErrorSeverity

logger = logging.getLogger(__name__)


@register_node("Assemble abbreviation catalogue")
async def assemble_catalogue_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    main_file = await runtime.context.file_artifacts_service.get_main_file()
    lines = (main_file.markdown or "").split("\n") if main_file else []

    catalogue = assemble_catalogue(
        state.chunks,
        state.abbreviations_section_entries,
        state.abbreviations_section_ranges,
        lines,
    )
    summary = _summary(state, catalogue, len(lines))
    logger.info(f"[AbbreviationScanV2] {summary}")

    return {
        "abbreviations": catalogue,
        "reasoning": summary,
        "errors": _chunk_errors(
            state.chunks, catalogue, runtime.context.workflow_run_id
        ),
    }


def _summary(
    state: AbbreviationScanV2State, catalogue: List[AbbreviationItem], total_lines: int
) -> str:
    extracted = [c for c in state.chunks if c.status != ChunkStatus.SKIPPED]
    failed = [c for c in extracted if c.status == ChunkStatus.ERROR]
    partial = [c for c in extracted if c.status == ChunkStatus.PARTIAL]
    distinct = len({item.abbr for item in catalogue})
    if state.abbreviations_section_found:
        spans = ", ".join(
            f"{r.start_line}-{r.end_line}" for r in state.abbreviations_section_ranges
        )
        section = (
            f"Abbreviations section at lines {spans} with "
            f"{len(state.abbreviations_section_entries)} entries."
        )
    else:
        section = "No Abbreviations section found."
    return (
        f"Scanned {total_lines} lines in {len(extracted)} chunks "
        f"({len(failed)} failed, {len(partial)} truncated). "
        f"Recorded {len(catalogue)} occurrences of {distinct} distinct abbreviations. "
        f"{section}"
    )


def _chunk_errors(
    chunks: List[AbbreviationChunk],
    catalogue: List[AbbreviationItem],
    workflow_run_id: str | None,
) -> List[WorkflowError]:
    """One error per failed or truncated chunk.

    A failed chunk costs part of the document, not the run, so these are
    warnings while the rest of the document still yielded a catalogue. When
    the catalogue is empty, it would read as an all-clear even though part of
    the document was never scanned, so the failures escalate to errors. A
    chunk that completed with no occurrences does not count as usable output
    on its own.
    """
    extracted = [c for c in chunks if c.status != ChunkStatus.SKIPPED]
    usable = bool(catalogue) and any(c.produced_results for c in extracted)
    severity = WorkflowErrorSeverity.WARNING if usable else WorkflowErrorSeverity.ERROR
    return [
        WorkflowError(
            chunk_index=chunk.chunk_index,
            task_name="extract_chunk",
            error=_chunk_error_message(chunk),
            workflow_run_id=workflow_run_id,
            severity=severity,
            details=chunk.error_details,
        )
        for chunk in extracted
        if chunk.status in (ChunkStatus.ERROR, ChunkStatus.PARTIAL)
    ]


def _chunk_error_message(chunk: AbbreviationChunk) -> str:
    where = f"Lines {chunk.start_line}-{chunk.end_line}"
    if chunk.status == ChunkStatus.PARTIAL:
        return (
            f"{where} returned truncated output. {len(chunk.occurrences)} "
            "abbreviation occurrence(s) were recovered; the rest are missing from "
            "these results, and an abbreviation first defined there may be flagged "
            "as undefined at a later use."
        )
    return (
        f"{where} could not be scanned for abbreviations. Their occurrences are "
        "missing from these results, and an abbreviation first defined there may be "
        f"flagged as undefined at a later use. {chunk.error or 'Unknown error'}"
    )
