"""Tests for combining chunk extractions into the document-wide catalogue."""

from typing import List, Optional

from lib.workflows.abbreviation_scan_v2.catalogue import assemble_catalogue
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    AbbreviationSectionEntry,
    ChunkOccurrence,
    ChunkStatus,
    LineRange,
)

# Every line mentions every abbreviation used below, so the check that an
# occurrence is really on its line passes unless a test says otherwise.
LINES = ["NATO, EU, OSCE, AI, LLMs, UN, FDA, Dr. and cm; NATO again"] * 40
LINES[19] = "## A heading with NATO"  # line 20
LINES[24] = "## Introduction"  # line 25
LINES[26] = "Spending on R&amp;D rose."  # line 27
LINES[27] = "Samples tested positive for Escherichia coli; a modified E. coli strain followed."  # line 28


def _occ(
    abbr: str,
    line: int,
    inline_definition: str = "",
    ignored: bool = False,
    ignored_reason: Optional[str] = None,
) -> ChunkOccurrence:
    return ChunkOccurrence(
        abbr=abbr,
        inline_definition=inline_definition,
        line_start=line,
        line_end=line,
        ignored=ignored,
        ignored_reason=ignored_reason,
    )


def _chunk(
    index: int,
    start: int,
    end: int,
    occurrences: List[ChunkOccurrence],
    status: ChunkStatus = ChunkStatus.COMPLETED,
) -> AbbreviationChunk:
    return AbbreviationChunk(
        chunk_index=index,
        start_line=start,
        end_line=end,
        status=status,
        occurrences=occurrences,
    )


def _assemble(chunks, entries=None, section_ranges=None):
    return assemble_catalogue(chunks, entries or [], section_ranges or [], LINES)


def test_occurrence_numbers_are_counted_across_chunks_in_document_order():
    catalogue = _assemble(
        [
            # Out of order on purpose: the reducer sorts, but the catalogue
            # must not depend on it.
            _chunk(1, 11, 19, [_occ("NATO", 12), _occ("EU", 15)]),
            _chunk(0, 1, 10, [_occ("NATO", 3, "North Atlantic Treaty Organization"), _occ("NATO", 7)]),
        ]
    )
    assert [(i.abbr, i.line_start, i.occurrence_number) for i in catalogue] == [
        ("NATO", 3, 1),
        ("NATO", 7, 2),
        ("NATO", 12, 3),
        ("EU", 15, 1),
    ]
    assert catalogue[0].inline_definition == "North Atlantic Treaty Organization"


def test_same_line_occurrences_keep_reading_order():
    catalogue = _assemble([_chunk(0, 1, 10, [_occ("NATO", 5), _occ("OSCE", 5), _occ("NATO", 5)])])
    assert [(i.abbr, i.occurrence_number) for i in catalogue] == [("NATO", 1), ("OSCE", 1), ("NATO", 2)]


def test_section_definitions_are_attached_including_plural_listings():
    entries = [
        AbbreviationSectionEntry(abbr="AI", definition="Artificial Intelligence"),
        AbbreviationSectionEntry(abbr="LLMs", definition="Large Language Models"),
    ]
    catalogue = _assemble([_chunk(0, 1, 10, [_occ("AI", 2), _occ("LLM", 3), _occ("EU", 4)])], entries)
    assert [i.abbreviations_section_definition for i in catalogue] == [
        "Artificial Intelligence",
        "Large Language Models",
        None,
    ]


def test_plural_is_folded_onto_a_singular_recorded_elsewhere():
    catalogue = _assemble(
        [
            _chunk(0, 1, 10, [_occ("LLM", 2, "Large Language Model")]),
            _chunk(1, 11, 19, [_occ("LLMs", 12)]),
        ]
    )
    assert [(i.abbr, i.occurrence_number) for i in catalogue] == [("LLM", 1), ("LLM", 2)]


def test_failed_and_skipped_chunks_contribute_nothing_but_partial_ones_do():
    catalogue = _assemble(
        [
            _chunk(0, 1, 10, [_occ("AI", 2)], status=ChunkStatus.ERROR),
            _chunk(1, 11, 19, [_occ("EU", 12)], status=ChunkStatus.PARTIAL),
            _chunk(2, 21, 30, [_occ("UN", 22)], status=ChunkStatus.SKIPPED),
        ]
    )
    assert [i.abbr for i in catalogue] == ["EU"]


def test_heading_occurrences_are_forced_to_ignored():
    catalogue = _assemble([_chunk(0, 11, 20, [_occ("NATO", 20), _occ("EU", 12)])])
    assert [(i.abbr, i.ignored, i.ignored_reason) for i in catalogue] == [
        ("EU", False, None),
        ("NATO", True, "Appears in a heading."),
    ]


def test_model_exemptions_are_kept_and_given_a_reason_when_missing():
    catalogue = _assemble(
        [_chunk(0, 1, 10, [_occ("Dr.", 2, ignored=True, ignored_reason="Personal title"), _occ("cm", 3, ignored=True)])]
    )
    assert [(i.ignored, i.ignored_reason) for i in catalogue] == [
        (True, "Personal title"),
        (True, "Excluded as an exempt occurrence."),
    ]


def test_occurrences_inside_the_abbreviations_section_are_dropped():
    catalogue = _assemble(
        [_chunk(0, 1, 10, [_occ("AI", 4), _occ("AI", 8)])],
        section_ranges=[LineRange(start_line=3, end_line=5)],
    )
    assert [(i.line_start, i.occurrence_number) for i in catalogue] == [(8, 1)]


def test_occurrences_outside_the_chunk_and_blank_abbrs_are_dropped():
    # The agent may read around its range; what it records out there belongs
    # to the neighbouring chunk, which records it too.
    catalogue = _assemble(
        [
            _chunk(0, 1, 10, [_occ("AI", 12), _occ("  ", 3), _occ("EU", 4)]),
            _chunk(1, 11, 19, [_occ("AI", 12)]),
        ]
    )
    assert [(i.abbr, i.line_start, i.occurrence_number) for i in catalogue] == [("EU", 4, 1), ("AI", 12, 1)]


def test_occurrences_not_on_their_reported_lines_are_dropped():
    catalogue = _assemble(
        [_chunk(0, 20, 30, [_occ("NATO", 20), _occ("ML", 25), _occ("Ph.D.", 26), _occ("R&D", 27)])]
    )
    assert [i.abbr for i in catalogue] == ["NATO", "R&D"]


def test_entries_beyond_the_times_an_abbreviation_appears_on_the_line_are_dropped():
    # Line 28 spells out "Escherichia coli" once and uses "E. coli" once; line 5
    # uses NATO twice, so both of its NATO entries stay.
    catalogue = _assemble(
        [_chunk(0, 1, 30, [_occ("NATO", 5), _occ("NATO", 5), _occ("E. coli", 28), _occ("E. coli", 28)])]
    )
    assert [(i.abbr, i.line_start) for i in catalogue] == [("NATO", 5), ("NATO", 5), ("E. coli", 28)]
