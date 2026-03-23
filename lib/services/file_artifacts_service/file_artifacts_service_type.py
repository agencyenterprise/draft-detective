from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from lib.workflows.chunk_utils import AnalyzedChunk
    from lib.models.bibliography_item import BibliographyItem
    from lib.models.footnote_item import FootnoteItem
    from lib.services.file import FileDocument
    from lib.workflows.document_summarization.state import FileSummary
    from lib.workflows.reference_extraction.state import ExtractedReference


class FileArtifactsServiceType(ABC):
    @abstractmethod
    async def get_file_document(self, file_id: str) -> "FileDocument": ...

    @abstractmethod
    async def get_main_file(self) -> "FileDocument": ...

    @abstractmethod
    async def get_supporting_files(self) -> list["FileDocument"]: ...

    @abstractmethod
    async def get_file_summary(self, file_id: str) -> "FileSummary": ...

    @abstractmethod
    async def get_extracted_references(self) -> list["ExtractedReference"]: ...

    @abstractmethod
    async def get_references(self) -> list["BibliographyItem"]: ...

    @abstractmethod
    async def get_chunks(self) -> list["AnalyzedChunk"]: ...

    @abstractmethod
    async def get_footnotes(self) -> list["FootnoteItem"]: ...

    @abstractmethod
    async def get_deepagent_backend_files(
        self,
        include_supporting_files: bool = True,
        include_skills: bool = True,
    ) -> dict[str, Any]: ...

    def get_paragraph_chunks(
        self, chunks: List["AnalyzedChunk"], paragraph_index: int
    ) -> List["AnalyzedChunk"]:
        """Get all the chunks for a given paragraph index."""

        return [chunk for chunk in chunks if chunk.paragraph_index == paragraph_index]

    def get_paragraph_text(
        self, chunks: List["AnalyzedChunk"], paragraph_index: int
    ) -> str:
        """Get the full paragraph text for a given paragraph index."""

        paragraph_chunks = [
            chunk for chunk in chunks if chunk.paragraph_index == paragraph_index
        ]
        return "\n".join([chunk.content for chunk in paragraph_chunks])
