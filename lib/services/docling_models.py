"""
Docling document models for rendering

Simplified models that pass through Docling's json_content as-is,
similar to docling-ts approach: https://github.com/docling-project/docling-ts
"""

import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


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

    model_config = ConfigDict(extra="allow")

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Override to include extra fields at top level.
        Centralized method for consistent document dict extraction.
        """
        data = super().model_dump(**kwargs)
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


class DoclingPageInfo(BaseModel):
    """Minimal page info for frontend rendering

    Only includes the fields actually used by the frontend.
    Note: Docling documents may use either 'page' or 'page_no' field.
    """

    page: Optional[int] = None
    page_no: Optional[int] = None
    width: Optional[float] = None
    height: Optional[float] = None


def _extract_page_dimensions(
    page_data: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """Extract width and height from page data, handling both nested and flat structures"""
    size = page_data.get("size", {})
    if isinstance(size, dict):
        return size.get("width"), size.get("height")
    return page_data.get("width"), page_data.get("height")


def extract_page_info_from_docling(
    docling_doc: Optional[DoclingDocument],
) -> Optional[List[DoclingPageInfo]]:
    """
    Extract minimal page info from a DoclingDocument for frontend rendering.

    Args:
        docling_doc: The full Docling document with all content

    Returns:
        List of DoclingPageInfo with just page numbers and dimensions, or None if no pages
    """
    if not docling_doc:
        logger.debug("No Docling document provided for page extraction")
        return None

    doc_dict = docling_doc.model_dump()
    pages_data = doc_dict.get("pages", {})

    if not pages_data:
        logger.warning(
            f"Docling document has no pages data. Available keys: {list(doc_dict.keys())}"
        )
        return None

    pages_list = list(pages_data.values())

    page_info_list = []
    for page_data in pages_list:
        width, height = _extract_page_dimensions(page_data)

        page_info_list.append(
            DoclingPageInfo(
                page=page_data.get("page"),
                page_no=page_data.get("page_no"),
                width=width,
                height=height,
            )
        )

    if not page_info_list:
        logger.warning("Extracted 0 pages from Docling document")
    else:
        logger.debug(f"Extracted {len(page_info_list)} pages from Docling document")

    return page_info_list if page_info_list else None
