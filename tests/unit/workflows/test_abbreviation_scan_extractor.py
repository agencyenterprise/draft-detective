from lib.workflows.abbreviation_scan.nodes.scan_abbreviations import (
    extract_abbreviations_from_chunks,
)
from lib.workflows.chunk_utils import AnalyzedChunk


def test_extracts_definitions_and_acronyms():
    chunks = [
        AnalyzedChunk(
            start_line=1,
            end_line=1,
            chunk_index=0,
            paragraph_index=0,
            headings=["Introduction"],
            content="Artificial Intelligence (AI) is here.",
        ),
        AnalyzedChunk(
            chunk_index=1,
            start_line=1,
            end_line=2,
            paragraph_index=1,
            headings=["Introduction"],
            content="RAND and NATO are organizations.",
        ),
        AnalyzedChunk(
            start_line=2,
            end_line=3,
            chunk_index=2,
            paragraph_index=2,
            headings=["Introduction"],
            content="We use AI and RAND in this paper.",
        ),
    ]

    items = extract_abbreviations_from_chunks(chunks)
    abbrs = [i.abbr for i in items]

    assert "AI" in abbrs
    assert "RAND" in abbrs
    assert "NATO" in abbrs

    ai_item = next(i for i in items if i.abbr == "AI")
    assert ai_item.is_definition is True
    assert ai_item.definition == "Artificial Intelligence"
    assert ai_item.chunk_index == 0


def test_dedup_prefers_definition():
    chunks = [
        AnalyzedChunk(
            start_line=1,
            end_line=1,
            chunk_index=0,
            paragraph_index=0,
            headings=["Intro"],
            content="We mention AI here.",
        ),
        AnalyzedChunk(
            start_line=1,
            end_line=2,
            chunk_index=1,
            paragraph_index=1,
            headings=["Intro"],
            content="Artificial Intelligence (AI) is defined here.",
        ),
        AnalyzedChunk(
            start_line=2,
            end_line=3,
            chunk_index=2,
            paragraph_index=2,
            headings=["Intro"],
            content="AI appears again.",
        ),
    ]

    items = extract_abbreviations_from_chunks(chunks)
    assert [i.abbr for i in items] == ["AI"]
    assert items[0].is_definition is True
    assert items[0].definition == "Artificial Intelligence"


def test_excludes_reference_section_chunks_by_heading_keywords():
    chunks = [
        AnalyzedChunk(
            start_line=1,
            end_line=1,
            chunk_index=0,
            paragraph_index=0,
            headings=["Intro"],
            content="Artificial Intelligence (AI) is here.",
        ),
        AnalyzedChunk(
            start_line=1,
            end_line=2,
            chunk_index=1,
            paragraph_index=10,
            headings=["References"],
            content="Some reference text mentioning NATO.",
        ),
        AnalyzedChunk(
            start_line=2,
            end_line=3,
            chunk_index=2,
            paragraph_index=11,
            headings=["References", "More"],
            content="More refs with RAND.",
        ),
    ]

    items = extract_abbreviations_from_chunks(chunks)
    assert [i.abbr for i in items] == ["AI"]
