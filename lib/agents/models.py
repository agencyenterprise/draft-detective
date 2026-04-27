# lib/agents/enums.py
from enum import Enum
from langchain_core.documents import Document
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


class DocumentMetadata(BaseModel):
    """Validated metadata for document chunks."""

    paragraph_index: int = Field(ge=0, description="Zero-based index of the paragraph")
    chunk_index: int = Field(ge=0, description="Zero-based global chunk index")
    chunk_index_within_paragraph: int = Field(
        ge=0, description="Zero-based index within the paragraph"
    )
    headings: Optional[list[str]] = Field(
        default=None,
        description="The headings associated with the paragraph, in order of hierarchy",
    )
    start_line: int = Field(ge=1, description="1-indexed starting line in markdown")
    end_line: int = Field(ge=1, description="1-indexed ending line in markdown")

    @field_validator("paragraph_index", "chunk_index", "chunk_index_within_paragraph")
    @classmethod
    def validate_indices(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Indices must be non-negative")
        return v


class ValidatedDocument(Document):
    """Document with validated metadata using Pydantic."""

    metadata: DocumentMetadata = Field(...)  # type: ignore[assignment]

    def __init__(self, page_content: str, **kwargs: Any) -> None:
        metadata_arg = kwargs.pop("metadata", None)

        if isinstance(metadata_arg, DocumentMetadata):
            metadata = metadata_arg
        else:
            metadata = DocumentMetadata(**(metadata_arg or {}))

        super().__init__(page_content=page_content, metadata=metadata, **kwargs)


class ChunkWithIndex(BaseModel):
    content: str
    chunk_index: int
    paragraph_index: int
    headings: Optional[list[str]] = Field(
        default=None,
        description="The headings associated with the chunk, in order of hierarchy",
    )
    start_line: int = Field(ge=1, description="1-indexed starting line in markdown")
    end_line: int = Field(ge=1, description="1-indexed ending line in markdown")


class ClaimCategory(str, Enum):
    ESTABLISHED = "established_reported_knowledge"
    METHODOLOGY = "methodology_procedural"
    RESULTS = "empirical_analytical_results"
    INTERPRETATION = "inferential_interpretive_claims"
    META = "meta_structural_evaluative"
    OTHER = "other"


class ReproducibilityCategory(str, Enum):
    """Reproducibility classification for methodologies and results."""

    FULLY_REPRODUCIBLE = "fully_reproducible"
    REPRODUCIBLE_WITH_WEB_SEARCH = "reproducible_with_web_search"
    REPRODUCIBLE_WITH_EXTERNAL_UPLOADS = "reproducible_with_external_uploads"
    NOT_REPRODUCIBLE = "not_reproducible"
