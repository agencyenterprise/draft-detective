"""Tests for the Abbreviations-section pre-check."""

import pytest

from lib.workflows.abbreviation_scan_v2.section_candidates import find_candidate_lines


@pytest.mark.parametrize(
    "line",
    [
        "## Abbreviations",
        "**ACRONYMS**",
        "| Acronym | Definition |",
        "Glossary",
        # A converted PDF: the running header glued onto the section title.
        "Securing AI Model Weights: Preventing Theft and Misuse of Frontier ModelsAbbreviations",
        "Abbreviations . . . . . . . . . . . . . . . . . . . . . . . . . . 12",
    ],
)
def test_lines_naming_the_section_are_candidates(line: str) -> None:
    assert find_candidate_lines(f"# Report\n\n{line}\n\nText.") == [3]


@pytest.mark.parametrize(
    "line",
    ["# Burden Sharing Among Allies", "DTSA reviews export licenses under ITAR and the EAR."],
)
def test_other_lines_are_not(line: str) -> None:
    assert find_candidate_lines(f"# Report\n\n{line}") == []


def test_line_numbers_are_one_indexed_across_the_document() -> None:
    markdown = "# Contents\nAbbreviations ..... 12\n\nBody.\n\n## Abbreviations\n\n- NATO: North Atlantic Treaty Organization"
    assert find_candidate_lines(markdown) == [2, 6]
