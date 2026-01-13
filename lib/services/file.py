import mimetypes
import os
from typing import List, Optional

from langchain_core.messages.utils import count_tokens_approximately
from pydantic import BaseModel, Field, computed_field, field_serializer

from lib.services.converters.base import convert_to_markdown
from lib.services.docling_models import (
    DoclingDocument,
    DoclingPageInfo,
    extract_page_info_from_docling,
)


class FileDocument(BaseModel):
    file_name: str = Field(
        description="The original name of the uploaded file, as saved in the user file system"
    )
    file_path: str = Field(
        description="The path to the uploaded file, as saved in the file system"
    )
    original_file_path: Optional[str] = Field(
        default=None,
        description="Path to the original file if it was converted (e.g., original .docx before PDF conversion)",
    )
    file_type: str = Field(description="The MIME type of the uploaded file")
    markdown: str = Field(description="The uploaded file content converted to markdown")
    markdown_token_count: int = Field(
        description="The approximate number of tokens in the markdown content"
    )
    file_id: str = Field(
        description="The UUID of the file record in the database",
    )
    docling_document: Optional[DoclingDocument] = Field(
        default=None,
        description="Full Docling document for internal processing (chunk mapping, etc.)",
    )

    @computed_field
    @property
    def docling_pages(self) -> Optional[List[DoclingPageInfo]]:
        """Computed from docling_document for API responses"""
        return extract_page_info_from_docling(self.docling_document)

    @field_serializer("docling_document")
    def _serialize_docling_document(self, value, _info):
        """Exclude from JSON, keep in Python serialization"""
        return None if _info.mode == "json" else value

    def __hash__(self):
        return hash((self.file_path))

    def __eq__(self, other):
        if not isinstance(other, FileDocument):
            return NotImplemented

        return self.file_path == other.file_path


async def create_file_document_from_path(
    file_path: str,
    file_id: str,
    file_type: Optional[str] = None,
    original_file_name: Optional[str] = None,
    original_file_path: Optional[str] = None,
    markdown_convert: bool = True,
) -> FileDocument:
    # Verify file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")

    file_name = original_file_name or os.path.basename(file_path)
    file_type = file_type or mimetypes.guess_type(file_name)[0] or "text/plain"

    markdown = await convert_to_markdown(file_path) if markdown_convert else ""
    markdown_token_count = count_tokens_approximately([markdown])

    file_document = FileDocument(
        file_id=file_id,
        file_path=str(file_path),
        file_name=file_name,
        file_type=file_type,
        markdown=markdown,
        markdown_token_count=markdown_token_count,
        original_file_path=original_file_path,
    )

    return file_document
