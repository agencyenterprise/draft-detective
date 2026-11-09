"""Bibliography item model for reference extraction."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from lib.services.files.document import FileDocument


class BibliographyItem(BaseModel):
    """Represents a bibliographic reference item extracted from a document."""

    text: str = Field(description="The text of the bibliographic item")
    file_id: str | None = Field(
        default=None,
        description="The UUID of the associated supporting document file in the database (if matched)",
    )
    reference_id: str | None = Field(
        default=None,
        description="The ID of the underlying ExtractedReference, when available.",
    )


def get_associated_supporting_file(
    reference: BibliographyItem,
    supporting_files: list["FileDocument"],
) -> "FileDocument | None":
    """
    Get the supporting file associated with a bibliography reference.

    Args:
        reference: The bibliography item to find the associated file for
        supporting_files: List of all supporting files

    Returns:
        The associated FileDocument if found, None otherwise
    """
    if not reference.file_id:
        return None

    return next(
        (f for f in supporting_files if f.file_id == reference.file_id),
        None,
    )
