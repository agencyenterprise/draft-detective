from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from lib.models.file import FileRole
from lib.services.files.document import FileDocument


class UnreadableDocument(BaseModel):
    """A chosen document that could not be read, and why."""

    file_id: str
    file_name: str
    reason: str


class LoadedDocuments(BaseModel):
    """The documents that loaded, and the ones that did not."""

    documents: list[FileDocument]
    unreadable: list[UnreadableDocument] = Field(default_factory=list)


if TYPE_CHECKING:
    from lib.models.bibliography_item import BibliographyItem
    from lib.workflows.document_summarization.state import FileSummary
    from lib.workflows.reference_extraction.state import ExtractedReference


class FileArtifactsServiceType(ABC):
    @abstractmethod
    async def get_file_document(self, file_id: str) -> "FileDocument": ...

    @abstractmethod
    async def get_main_file(self, revision: int | None = None) -> "FileDocument": ...

    @abstractmethod
    async def get_project_files(
        self, roles: list[FileRole], revision: int | None = None
    ) -> list["FileDocument"]: ...

    @abstractmethod
    async def get_file_summary(self, file_id: str) -> "FileSummary": ...

    @abstractmethod
    async def get_extracted_references(self) -> list["ExtractedReference"]: ...

    @abstractmethod
    async def get_references(self) -> list["BibliographyItem"]: ...

    @abstractmethod
    async def get_file_documents(self, file_ids: list[str]) -> "LoadedDocuments": ...

    @abstractmethod
    async def get_deepagent_backend_files(
        self,
        include_skills: bool = True,
    ) -> dict[str, Any]: ...
