"""The downloader fetches only the references no supporting file is matched to."""

import pytest

from lib.models.bibliography_item import BibliographyItem
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.reference_downloader.nodes.fetch_references import (
    _load_unmatched_references,
)


@pytest.mark.asyncio
async def test_skips_matched_references_and_those_without_an_id() -> None:
    service = MockFileArtifactsService(
        references=[
            BibliographyItem(text="Smith 2020", reference_id="ref-1"),
            BibliographyItem(text="Doe 2019", reference_id="ref-2", file_id="f"),
            BibliographyItem(text="Lee 2018"),
        ]
    )

    items = await _load_unmatched_references(service)

    assert [(i.reference_id, i.text) for i in items] == [("ref-1", "Smith 2020")]
