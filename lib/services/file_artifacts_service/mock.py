from lib.agents.document_summarizer import DocumentSummary
from lib.models.bibliography_item import BibliographyItem
from lib.models.footnote_item import FootnoteItem
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.chunk_utils import AnalyzedChunk


class MockFileArtifactsService(FileArtifactsServiceType):
    async def get_file_document(self, file_id: str) -> FileDocument:
        return FileDocument(file_id=file_id)

    async def get_main_file(self) -> FileDocument:
        return FileDocument(file_id="main_file_id")

    async def get_supporting_files(self) -> list[FileDocument]:
        return [FileDocument(file_id="supporting_file_id")]

    async def get_document_summary(self, file_id: str) -> DocumentSummary:
        return DocumentSummary(
            title="Mock Title",
            authors="Mock Authors",
            publication_date="Mock Publication Date",
            abstract="Mock Abstract",
            summary="Mock Summary",
        )

    async def get_references(self) -> list[BibliographyItem]:
        return []

    async def get_chunks(self) -> list[AnalyzedChunk]:
        return []

    async def get_footnotes(self) -> list[FootnoteItem]:
        return []
