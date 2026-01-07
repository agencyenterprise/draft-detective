"""Service to map document chunks to DOCX paragraphs.

Maps chunks back to their original DOCX paragraph locations using
sequential forward-only text matching to handle duplicate text correctly.
"""

import logging
from typing import Dict, List, Protocol

from docx.text.paragraph import Paragraph

from lib.services.text_matching import text_matches

logger = logging.getLogger(__name__)


class ChunkLike(Protocol):
    """Protocol for objects that can be mapped to DOCX paragraphs."""

    content: str
    chunk_index: int


def create_chunk_to_paragraph_mapping(
    chunks: List[ChunkLike],
    docx_paragraphs: List[Paragraph],
) -> Dict[int, int]:
    """Map chunk_index to DOCX paragraph index using sequential forward matching.

    Args:
        chunks: List of chunk-like objects with content and chunk_index
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

    sorted_chunks = sorted(chunks, key=lambda c: getattr(c, 'chunk_index', c.metadata.chunk_index))
    min_search_idx = 0

    for chunk in sorted_chunks:
        chunk_text = getattr(chunk, 'content', chunk.page_content).strip()
        if not chunk_text:
            continue

        chunk_idx = getattr(chunk, 'chunk_index', chunk.metadata.chunk_index)

        # Primary: search forward only from current position
        for para_idx in range(min_search_idx, len(docx_paragraphs)):
            if text_matches(chunk_text, docx_paragraphs[para_idx].text):
                mapping[chunk_idx] = para_idx
                min_search_idx = para_idx
                break
        else:
            # Fallback: search from beginning if forward search fails
            for para_idx in range(0, min_search_idx):
                if text_matches(chunk_text, docx_paragraphs[para_idx].text):
                    mapping[chunk_idx] = para_idx
                    logger.debug(
                        f"Chunk {chunk_idx} matched paragraph {para_idx} via fallback"
                    )
                    break
            else:
                logger.warning(
                    f"No match for chunk {chunk_idx}: '{chunk_text[:60]}...'"
                )

    logger.info(f"Mapped {len(mapping)}/{len(chunks)} chunks to DOCX paragraphs")
    return mapping
