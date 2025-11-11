"""
Docling document models for rendering

Simplified models that pass through Docling's json_content as-is,
similar to docling-ts approach: https://github.com/docling-project/docling-ts
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box coordinates (bottom-left origin as per PDF standard)"""

    x0: float
    y0: float
    x1: float
    y1: float


class DoclingRegion(BaseModel):
    """Region mapping for frontend overlay"""

    id: str
    page: int
    bbox: BBox
    kind: str = Field(description="Item type: text, table, picture, kv")


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
