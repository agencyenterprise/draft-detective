"""Footnote item model for footnote extraction."""

from typing import Optional

from pydantic import BaseModel, Field


class FootnoteItem(BaseModel):
    """Represents a footnote extracted from a document."""

    marker: str = Field(
        description="The footnote number/marker (e.g., '160', '1', '107')"
    )

    text: str = Field(description="The full text content of the footnote")

    reference_code: Optional[str] = Field(
        default=None,
        description="The reference code/anchor (e.g., '#footnote-ref-161'). Stored as metadata only, no document linking.",
    )
