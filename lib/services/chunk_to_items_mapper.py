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
from lib.services.text_matching import text_matches

logger = logging.getLogger(__name__)

DOCLING_COLLECTIONS = ["texts", "tables", "pictures", "key_value_items"]


def _collect_docling_items(doc_dict: Dict) -> List[DoclingItem]:
    """
    Collect and parse all items from Docling document

    Items are collected in document order from the collections.

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


def create_chunk_to_items_mapping(
    chunks: List[ValidatedDocument],
    docling_document: DoclingDocument,
) -> ChunkToItems:
    """
    Map chunks to Docling items using sequential forward matching.

    Processes chunks in chunk_index order and searches items forward-only
    from last matched position. Uses fuzzy matching to handle text variations.
    Can match multiple items per chunk (for bbox regions).

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

    if not chunks or not all_items:
        logger.warning("Empty chunks or items provided, returning empty mapping")
        return mapping

    logger.info(f"Mapping {len(chunks)} chunks to {len(all_items)} Docling items")

    sorted_chunks = sorted(chunks, key=lambda c: c.metadata.chunk_index)

    min_search_idx = 0

    for chunk_doc in sorted_chunks:
        chunk_index = chunk_doc.metadata.chunk_index
        chunk_text = chunk_doc.page_content.strip()

        if not chunk_text:
            continue

        matched_count = 0

        for item_idx in range(min_search_idx, len(all_items)):
            item = all_items[item_idx]
            item_text = item.content

            if not item_text or not item.bbox:
                continue

            if not text_matches(chunk_text, item_text):
                continue

            region = DoclingRegion(
                id=item.self_ref or f"region-{chunk_index}",
                page=item.page_number,
                bbox=item.bbox,
            )
            mapping.add_item(chunk_index, region)
            matched_count += 1

            if matched_count == 1:
                min_search_idx = item_idx

        if matched_count == 0:
            logger.warning(f"No match for chunk {chunk_index}: '{chunk_text}...'")
        else:
            logger.debug(f"Chunk {chunk_index}: matched {matched_count} items")

    mapped_chunks = sum(1 for items in mapping.mapping.values() if items)
    logger.info(f"Mapped {mapped_chunks}/{len(chunks)} chunks to Docling items")

    return mapping
