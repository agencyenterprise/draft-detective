"""
Service to map document chunks to Docling items/regions
"""

import logging
from typing import Dict, List

from pydantic import ValidationError

from lib.agents.models import ValidatedDocument
from lib.services.docling_models import (
    ChunkToItems,
    DoclingDocument,
    DoclingItem,
    DoclingRegion,
)

logger = logging.getLogger(__name__)

# Docling document collections to iterate
DOCLING_COLLECTIONS = ["texts", "tables", "pictures", "key_value_items"]


def _collect_docling_items(doc_dict: Dict) -> List[DoclingItem]:
    """
    Collect and parse all items from Docling document

    Returns list of DoclingItem objects
    """
    items = []

    for collection_name in DOCLING_COLLECTIONS:
        for item_dict in doc_dict.get(collection_name, []):
            if "$ref" in item_dict:
                continue
            try:
                item = DoclingItem.model_validate(item_dict)
                items.append(item)
            except ValidationError as e:
                logger.debug(f"Failed to parse {collection_name} item: {e}")

    return items


def _text_matches(chunk_text: str, item_text: str) -> bool:
    """Check if chunk and item text match via substring"""
    chunk_lower = chunk_text.lower().strip()
    item_lower = item_text.lower().strip()
    return chunk_lower in item_lower or item_lower in chunk_lower


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
        for item in all_items:
            item_text = item.content
            if not item_text or not _text_matches(chunk_text, item_text):
                continue

            # Create region if item has bbox
            if not item.bbox:
                continue

            region = DoclingRegion(
                id=item.self_ref or f"region-{chunk_index}",
                page=item.page_number,
                bbox=item.bbox,
            )
            mapping.add_item(chunk_index, region)
            matched_count += 1

        if matched_count:
            logger.debug(f"Chunk {chunk_index}: matched {matched_count} items")

    mapped_chunks = sum(1 for items in mapping.mapping.values() if items)
    logger.info(f"Mapped {mapped_chunks}/{len(chunks)} chunks to Docling items")

    return mapping
