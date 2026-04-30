"""Bibliography item model for reference extraction."""

from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from lib.services.file import FileDocument


class BibliographyItem(BaseModel):
    """Represents a bibliographic reference item extracted from a document."""

    text: str = Field(description="The text of the bibliographic item")
    has_associated_supporting_document: bool = Field(
        description="A boolean value indicating whether the bibliographic item has an associated supporting document provided by the user"
    )
    index_of_associated_supporting_document: int = Field(
        description="If the bibliographic item has an associated supporting document, this will be the index of the supporting document in the list of supporting documents provided by the user (index starts at 1), otherwise it will be -1."
    )
    name_of_associated_supporting_document: str = Field(
        description="If the bibliographic item has an associated supporting document, this will be the name of the supporting document, otherwise it will be an empty string."
    )
    file_id: Optional[str] = Field(
        default=None,
        description="The UUID of the associated supporting document file in the database (if matched)",
    )
    reference_id: Optional[str] = Field(
        default=None,
        description="The ID of the underlying ExtractedReference, when available.",
    )


def get_associated_supporting_file(
    reference: BibliographyItem,
    supporting_files: List["FileDocument"],
) -> Optional["FileDocument"]:
    """
    Get the supporting file associated with a bibliography reference.

    Args:
        reference: The bibliography item to find the associated file for
        supporting_files: List of all supporting files

    Returns:
        The associated FileDocument if found, None otherwise
    """
    if not reference.has_associated_supporting_document or not reference.file_id:
        return None

    return next(
        (f for f in supporting_files if f.file_id == reference.file_id),
        None,
    )
