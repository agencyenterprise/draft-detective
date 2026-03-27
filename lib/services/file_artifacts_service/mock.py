from typing import Any, Optional

from deepagents.backends.utils import create_file_data

from lib.models.bibliography_item import BibliographyItem
from lib.models.footnote_item import FootnoteItem
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.document_summarization.state import FileSummary
from lib.workflows.reference_extraction.state import ExtractedReference


class MockFileArtifactsService(FileArtifactsServiceType):
    """Mock file artifacts service for testing.

    Can be configured with actual data for more realistic tests:
        mock = MockFileArtifactsService(main_file=actual_file)
    """

    def __init__(
        self,
        main_file: Optional[FileDocument] = None,
        supporting_files: Optional[list[FileDocument]] = None,
        extracted_references: Optional[list[ExtractedReference]] = None,
        references: Optional[list[BibliographyItem]] = None,
    ):
        self._main_file = main_file
        self._supporting_files = supporting_files or []
        self._extracted_references = extracted_references or []
        self._references = references or []

    async def get_file_document(self, file_id: str) -> FileDocument:
        # Check if file matches main_file or any supporting file
        if self._main_file and self._main_file.file_id == file_id:
            return self._main_file
        for f in self._supporting_files:
            if f.file_id == file_id:
                return f
        return FileDocument(file_id=file_id)

    async def get_main_file(self) -> FileDocument:
        if self._main_file:
            return self._main_file
        return FileDocument(file_id="main_file_id")

    async def get_supporting_files(self) -> list[FileDocument]:
        if self._supporting_files:
            return self._supporting_files
        return []

    async def get_file_summary(self, file_id: str) -> FileSummary:
        return FileSummary(
            file_id=file_id,
            title="Mock Title",
            authors="Mock Authors",
            publication_date="Mock Publication Date",
            abstract="Mock Abstract",
            summary="Mock Summary",
        )

    async def get_extracted_references(self) -> list[ExtractedReference]:
        return self._extracted_references

    async def get_references(self) -> list[BibliographyItem]:
        return self._references

    async def get_chunks(self) -> list[AnalyzedChunk]:
        return []

    async def get_footnotes(self) -> list[FootnoteItem]:
        return []

    async def get_deepagent_backend_files(
        self,
        include_supporting_files: bool = True,
        include_skills: bool = True,
    ) -> dict[str, Any]:
        files = {"/main.md": create_file_data(self._main_file.markdown)}
        if include_supporting_files:
            files.update(
                {
                    f"/supporting/{f.file_id}.md": create_file_data(f.markdown)
                    for f in self._supporting_files
                }
            )
        return files
