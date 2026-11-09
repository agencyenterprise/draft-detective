"""The bibliography-to-file map the claim validator's prompt shows."""

from lib.models.bibliography_item import BibliographyItem
from lib.services.files.document import FileDocument
from lib.workflows.claim_reference_validation_v2.citation_mapping import (
    build_reference_file_map,
)


def _file(file_id: str, name: str) -> FileDocument:
    return FileDocument(
        file_name=name,
        file_path=name,
        file_type="application/pdf",
        markdown="",
        markdown_token_count=0,
        file_id=file_id,
    )


def test_lists_the_matched_file_or_its_absence() -> None:
    references = [
        BibliographyItem(text="Smith 2020", file_id="f-1"),
        BibliographyItem(text="Doe 2019"),
        BibliographyItem(text="Lee 2018", file_id="gone"),
    ]

    mapping = build_reference_file_map(references, [_file("f-1", "smith.pdf")])

    assert mapping.splitlines() == [
        '- "Smith 2020" → File: "smith.pdf" (file_id: f-1)',
        '- "Doe 2019" → No supporting file available',
        '- "Lee 2018" → No supporting file available',
    ]


def test_says_so_when_there_are_no_references() -> None:
    assert build_reference_file_map([], []) == "No bibliography entries available."
