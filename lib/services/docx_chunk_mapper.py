"""
Service to map document chunks to DOCX paragraphs.

Maps chunks back to their original DOCX paragraph locations using
sequential forward-only text matching to handle duplicate text correctly.
"""

import logging
from typing import Dict, List

from lib.agents.models import ValidatedDocument
from lib.services.text_matching import text_matches

logger = logging.getLogger(__name__)


def create_chunk_to_paragraph_mapping(
    chunks: List[ValidatedDocument], docx_paragraphs: List
) -> Dict[int, int]:
    """
    Map chunk_index to DOCX paragraph index using sequential forward matching.

    Processes chunks in document order and searches forward-only to ensure
    duplicate text maps to the correct paragraph by position.

    Args:
        chunks: List of document chunks with content and metadata
        docx_paragraphs: List of python-docx Paragraph objects

    Returns:
        Dictionary mapping {chunk_index: docx_paragraph_index}
    """
    mapping = {}

    if not chunks or not docx_paragraphs:
        logger.warning("Empty chunks or paragraphs provided, returning empty mapping")
        return mapping

    logger.info(
        f"Mapping {len(chunks)} chunks to {len(docx_paragraphs)} DOCX paragraphs"
    )

    sorted_chunks = sorted(chunks, key=lambda c: c.metadata.chunk_index)
    min_search_idx = 0

    for chunk in sorted_chunks:
        chunk_text = chunk.page_content.strip()
        if not chunk_text:
            continue

        chunk_idx = chunk.metadata.chunk_index

        # We must search forward only from current position
        for para_idx in range(min_search_idx, len(docx_paragraphs)):
            if text_matches(chunk_text, docx_paragraphs[para_idx].text):
                mapping[chunk_idx] = para_idx
                min_search_idx = para_idx
                break
        else:
            logger.debug(f"No forward match for chunk {chunk_idx}")

    logger.info(f"Mapped {len(mapping)}/{len(chunks)} chunks to DOCX paragraphs")
    return mapping
