"""Bibliography item model for reference extraction."""

from pydantic import BaseModel, Field


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

