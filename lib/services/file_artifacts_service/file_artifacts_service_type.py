from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, List

from lib.models.file import FileRole

if TYPE_CHECKING:
    from lib.models.bibliography_item import BibliographyItem
    from lib.services.file import FileDocument
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
    async def get_latest_reviewer_memo_revision(self) -> int | None: ...

    @abstractmethod
    async def get_file_summary(self, file_id: str) -> "FileSummary": ...

    @abstractmethod
    async def get_extracted_references(self) -> list["ExtractedReference"]: ...

    @abstractmethod
    async def get_references(self) -> list["BibliographyItem"]: ...

    @abstractmethod
    async def get_deepagent_backend_files(
        self,
        include_skills: bool = True,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_input_backend_files(
        self,
        input_files: dict[str, list[str]],
        include_skills: bool = True,
    ) -> dict[str, Any]: ...
