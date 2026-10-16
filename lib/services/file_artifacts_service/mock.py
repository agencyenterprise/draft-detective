from pathlib import Path
from typing import Any

from deepagents.backends.utils import create_file_data

from lib.models.bibliography_item import BibliographyItem
from lib.models.file import FileRole
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
    LoadedDocuments,
)
from lib.services.files.document import FileDocument
from lib.skills import strip_interactive_only
from lib.workflows.document_summarization.state import FileSummary
from lib.workflows.reference_extraction.state import ExtractedReference


def _empty_file_document(file_id: str) -> FileDocument:
    return FileDocument(
        file_id=file_id,
        file_name="",
        file_path="",
        file_type="",
        markdown="",
        markdown_token_count=0,
    )


class MockFileArtifactsService(FileArtifactsServiceType):
    """Mock file artifacts service for testing.

    Can be configured with actual data for more realistic tests:
        mock = MockFileArtifactsService(main_file=actual_file)
    """

    def __init__(
        self,
        main_file: FileDocument | None = None,
        supporting_files: list[FileDocument] | None = None,
        extracted_references: list[ExtractedReference] | None = None,
        references: list[BibliographyItem] | None = None,
        review_input_files: list[FileDocument] | None = None,
    ):
        self._main_file = main_file
        self._supporting_files = supporting_files or []
        self._extracted_references = extracted_references or []
        self._references = references or []
        self._review_input_files = review_input_files or []

    async def get_file_document(self, file_id: str) -> FileDocument:
        # Check if file matches main_file or any supporting file
        if self._main_file and self._main_file.file_id == file_id:
            return self._main_file
        for f in self._supporting_files:
            if f.file_id == file_id:
                return f
        return _empty_file_document(file_id)

    async def get_main_file(self, revision: int | None = None) -> FileDocument:
        if self._main_file:
            return self._main_file
        return _empty_file_document("main_file_id")

    async def get_project_files(
        self, roles: list[FileRole], revision: int | None = None
    ) -> list[FileDocument]:
        documents: list[FileDocument] = []
        if FileRole.SUPPORT in roles:
            documents.extend(self._supporting_files)
        return documents

    async def get_file_documents(self, file_ids: list[str]) -> LoadedDocuments:
        known = [
            *([self._main_file] if self._main_file else []),
            *self._supporting_files,
            *self._review_input_files,
        ]
        by_id = {f.file_id: f for f in known}
        return LoadedDocuments(documents=[by_id[i] for i in file_ids if i in by_id])

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

    async def get_deepagent_backend_files(
        self,
        include_skills: bool = True,
    ) -> dict[str, Any]:
        main_markdown = self._main_file.markdown if self._main_file else ""
        files: dict[str, Any] = {"/main.md": create_file_data(main_markdown)}

        for f in self._supporting_files:
            files[f"/supporting/{f.file_id}.md"] = create_file_data(f.markdown)

        # The mock has no revision metadata; place the main under a single
        # synthetic revision so the tree shape matches production.
        if self._main_file:
            files["/revisions/1/main.md"] = create_file_data(self._main_file.markdown)

        if include_skills:
            project_root = Path(__file__).parents[3]
            skills_dir = project_root / "skills"
            for skill_file in sorted(skills_dir.rglob("*")):
                if skill_file.is_file():
                    virtual_path = "/" + skill_file.relative_to(project_root).as_posix()
                    files[virtual_path] = create_file_data(
                        strip_interactive_only(skill_file.read_text())
                    )
        return files
