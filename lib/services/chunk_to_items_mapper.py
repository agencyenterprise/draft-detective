"""
Service to map document chunks to Docling items/regions
"""

import logging
from typing import Dict, List, Optional, Tuple

from lib.agents.models import ValidatedDocument
from lib.services.docling_models import (
    BBox,
    ChunkToItems,
    DoclingDocument,
    DoclingRegion,
)

logger = logging.getLogger(__name__)


def _collect_docling_items(doc_dict: Dict) -> List[Tuple[dict, str]]:
    """Collect all items from Docling document"""
    items = []
    for item in doc_dict.get("texts", []):
        items.append((item, "text"))
    for item in doc_dict.get("tables", []):
        items.append((item, "table"))
    for item in doc_dict.get("pictures", []):
        items.append((item, "picture"))
    for item in doc_dict.get("key_value_items", []):
        items.append((item, "kv"))
    return items


def _extract_item_text(item_dict: dict) -> str:
    """Extract text content from a Docling item"""
    if "text" in item_dict:
        return item_dict["text"]
    if "content" in item_dict:
        return item_dict["content"]
    return ""


def _extract_bbox(item_dict: dict) -> Optional[dict]:
    """Extract bbox data from item, checking multiple locations"""
    bbox_data = item_dict.get("bbox")
    if not bbox_data and "prov" in item_dict:
        prov_list = item_dict.get("prov", [])
        if prov_list:
            bbox_data = prov_list[0].get("bbox")

    # Handle bbox as list or dict
    if isinstance(bbox_data, list) and bbox_data:
        return bbox_data[0]
    return bbox_data


def _extract_page_number(item_dict: dict) -> int:
    """Extract page number from item metadata"""
    if "prov" in item_dict:
        prov_list = item_dict.get("prov", [])
        if prov_list:
            return prov_list[0].get("page_no", prov_list[0].get("page", 0))
    return item_dict.get("page", 0)


def _create_region(
    item_dict: dict, kind: str, fallback_id: str
) -> Optional[DoclingRegion]:
    """Create a DoclingRegion from item data"""
    bbox_data = _extract_bbox(item_dict)
    if not bbox_data:
        return None

    try:
        bbox = BBox(
            x0=bbox_data.get("l", bbox_data.get("x0", 0)),
            y0=bbox_data.get("b", bbox_data.get("y0", 0)),
            x1=bbox_data.get("r", bbox_data.get("x1", 0)),
            y1=bbox_data.get("t", bbox_data.get("y1", 0)),
        )

        return DoclingRegion(
            id=item_dict.get("self_ref", item_dict.get("id", fallback_id)),
            page=_extract_page_number(item_dict),
            bbox=bbox,
            kind=kind,
        )
    except Exception as e:
        logger.debug(f"Failed to create region: {e}")
        return None


def _text_matches(chunk_text: str, item_text: str) -> bool:
    """Check if chunk and item text match via substring or word overlap"""
    chunk_lower = chunk_text.lower().strip()
    item_lower = item_text.lower().strip()

    # Substring match
    if chunk_lower in item_lower or item_lower in chunk_lower:
        return True

    # Word overlap for shorter texts
    if len(chunk_lower) < 100 and len(item_lower) < 100:
        chunk_words = set(chunk_lower.split())
        item_words = set(item_lower.split())
        overlap = len(chunk_words & item_words)
        threshold = min(3, len(chunk_words) // 2)
        return overlap > threshold

    return False


def create_chunk_to_items_mapping(
    chunks: List[ValidatedDocument],
    docling_document: DoclingDocument,
) -> ChunkToItems:
    """
    Map chunks to Docling items based on text content matching

    Args:
        chunks: List of document chunks with content and metadata
        docling_document: Docling document with raw json_content

    Returns:
        ChunkToItems mapping with regions for overlay rendering
    """
    mapping = ChunkToItems()

    if not docling_document:
        logger.warning("No Docling document provided, returning empty mapping")
        return mapping

    doc_dict = docling_document.model_dump()
    all_items = _collect_docling_items(doc_dict)

    logger.info(f"Mapping {len(chunks)} chunks to {len(all_items)} Docling items")

    # Map each chunk to matching items based on text overlap
    for chunk_doc in chunks:
        chunk_index = chunk_doc.metadata.chunk_index
        chunk_text = chunk_doc.page_content.strip()

        if not chunk_text:
            continue

        matched_count = 0
        for item_dict, kind in all_items:
            # Skip references
            if "$ref" in item_dict:
                continue

            item_text = _extract_item_text(item_dict)
            if not item_text or not _text_matches(chunk_text, item_text):
                continue

            region = _create_region(item_dict, kind, f"{kind}-{chunk_index}")
            if region:
                mapping.add_item(chunk_index, region)
                matched_count += 1

        if matched_count:
            logger.debug(f"Chunk {chunk_index}: matched {matched_count} items")

    mapped_chunks = sum(1 for items in mapping.mapping.values() if items)
    logger.info(f"Mapped {mapped_chunks}/{len(chunks)} chunks to Docling items")

    return mapping
