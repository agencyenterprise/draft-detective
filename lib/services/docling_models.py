"""
Docling document models for rendering

Simplified models that pass through Docling's json_content as-is,
similar to docling-ts approach: https://github.com/docling-project/docling-ts
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class BBox(BaseModel):
    """Docling bounding box format (bottom-left origin, PDF standard)"""

    l: float  # left
    b: float  # bottom
    r: float  # right
    t: float  # top


class DoclingProv(BaseModel):
    """Provenance information for Docling items"""

    page_no: int
    bbox: BBox
    charspan: Optional[List[int]] = None


class DoclingItemReference(BaseModel):
    """Reference to another item in the document"""

    model_config = ConfigDict(populate_by_name=True)

    ref: str = Field(alias="$ref")


class DoclingItem(BaseModel):
    """
    A Docling document item (text, table, picture, etc.)

    Based on actual schema analysis:
    - text content is always in 'text' field
    - bbox is always in prov[0].bbox
    - page number is always in prov[0].page_no
    """

    model_config = ConfigDict(extra="allow")

    self_ref: Optional[str] = None
    label: Optional[str] = None
    text: Optional[str] = None
    orig: Optional[str] = None  # Original text before processing
    prov: List[DoclingProv] = Field(default_factory=list)
    parent: Optional[DoclingItemReference | Dict[str, Any]] = None

    @property
    def bbox(self) -> Optional[BBox]:
        """Get bbox from first provenance entry"""
        return self.prov[0].bbox if self.prov else None

    @property
    def page_number(self) -> int:
        """Get page number from first provenance entry"""
        return self.prov[0].page_no if self.prov else 0

    @property
    def content(self) -> str:
        """Get text content, preferring 'text' field over 'orig'"""
        return self.text or self.orig or ""


class DoclingRegion(BaseModel):
    """Region mapping for frontend overlay"""

    id: str
    page: int
    bbox: BBox


class DoclingDocument(BaseModel):
    """
    Raw Docling json_content passed through to frontend

    We don't parse/transform - just pass the structure as-is.
    Frontend will handle the Docling format directly.

    All fields from Docling's json_content are stored in __pydantic_extra__
    and serialized properly.
    """

    model_config = {"extra": "allow"}

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to include extra fields at top level"""
        data = super().model_dump(**kwargs)
        # Merge extra fields into the main dict
        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            data.update(self.__pydantic_extra__)
        return data

    @classmethod
    def from_json_content(cls, json_content: Dict[str, Any]) -> "DoclingDocument":
        """Create DoclingDocument from Docling's json_content dict"""
        return cls(**json_content)


class ChunkToItems(BaseModel):
    """
    Mapping from chunk indices to document items/regions

    Keys are string chunk indices, values are lists of regions
    """

    mapping: Dict[str, List[DoclingRegion]] = Field(
        default_factory=dict,
        description="Maps chunk_index (as string) to list of regions",
    )

    def add_item(self, chunk_index: int, region: DoclingRegion) -> None:
        """Add a region to a chunk's mapping"""
        key = str(chunk_index)
        if key not in self.mapping:
            self.mapping[key] = []
        self.mapping[key].append(region)

    def get_items(self, chunk_index: int) -> List[DoclingRegion]:
        """Get all regions for a chunk"""
        return self.mapping.get(str(chunk_index), [])
