"""Extract references with overlapping windows and incremental deduplication."""

import logging
from typing import List, Optional

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import format_supporting_documents_prompt_section_multiple
from lib.agents.reference_extractor import BibliographyItem, ReferenceExtractorAgent
from lib.services.text_matching import text_matches
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ReferenceExtractionState

logger = logging.getLogger(__name__)


def _create_overlapping_windows(
    chunks: List, start_idx: int, end_idx: int, window_size: int, overlap: int
) -> List[tuple]:
    """
    Create overlapping windows from chunk range.

    Returns list of (window_start, window_end) tuples.
    """
    windows = []
    current = start_idx

    while current < end_idx:
        window_end = min(current + window_size, end_idx)
        windows.append((current, window_end))

        # Move forward by (window_size - overlap)
        current += window_size - overlap

        # Prevent infinite loop
        if window_end >= end_idx:
            break

    return windows


def _check_if_duplicate(
    new_ref: BibliographyItem,
    existing_refs: List[BibliographyItem],
    threshold: float,
) -> tuple[bool, Optional[int]]:
    """
    Check if reference already exists using fuzzy matching.

    Returns: (is_duplicate, existing_index_if_duplicate)
    """
    for idx, existing_ref in enumerate(existing_refs):
        # Quick rejection filters
        new_text = new_ref.text.lower()
        existing_text = existing_ref.text.lower()

        # Check year mismatch (fast rejection)
        import re

        new_years = re.findall(r"\b(19|20)\d{2}\b", new_text)
        existing_years = re.findall(r"\b(19|20)\d{2}\b", existing_text)

        if new_years and existing_years:
            if not any(y in existing_years for y in new_years):
                continue  # Different years = different refs

        # Check length difference (fast rejection)
        len_diff = abs(len(new_text) - len(existing_text)) / max(
            len(new_text), len(existing_text)
        )
        if len_diff > 0.5:  # More than 50% length difference
            continue

        # Expensive fuzzy match
        if text_matches(new_text, existing_text, threshold=threshold):
            return True, idx

    return False, None


def _merge_reference_versions(
    existing_ref: BibliographyItem, new_ref: BibliographyItem
) -> BibliographyItem:
    """
    Merge two versions of the same reference, keeping the more complete one.
    """
    # Keep the longer version (usually more complete)
    if len(new_ref.text) > len(existing_ref.text):
        # New version is more complete
        return new_ref.model_copy(
            update={
                "has_associated_supporting_document": (
                    existing_ref.has_associated_supporting_document
                    or new_ref.has_associated_supporting_document
                ),
            }
        )
    else:
        # Keep existing (it's more complete)
        return existing_ref


@register_node(
    "Extract references with overlap",
    "Extract references using windowed extraction with deduplication",
)
async def extract_with_overlap(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> ReferenceExtractionState:
    """
    Extract references from detected sections using overlapping windows.

    Implements incremental deduplication: checks before adding each reference.
    """
    if not state.detected_sections:
        logger.warning("No sections detected, cannot extract references")
        return {"references": []}

    logger.info(
        f"Extracting references from {len(state.detected_sections)} sections "
        f"(window_size={state.config.window_size}, overlap={state.config.overlap_size})"
    )

    # Format supporting documents once
    supporting_documents = format_supporting_documents_prompt_section_multiple(
        state.supporting_files,
        truncate_at_character_count=state.config.truncate_supporting_docs_at,
    )

    # Create agent
    reference_extractor = ReferenceExtractorAgent(runtime.context)

    # Shared state: all extracted references (incremental deduplication)
    all_references: List[BibliographyItem] = []

    # Process each detected section
    for section in state.detected_sections:
        logger.info(
            f"Processing section: {section.section_type} "
            f"(chunks {section.start_chunk_index}-{section.end_chunk_index or 'end'})"
        )

        # Define section boundaries
        start_idx = max(0, section.start_chunk_index - 5)  # Add 5-chunk buffer before
        end_idx = (
            section.end_chunk_index + 5
            if section.end_chunk_index
            else len(state.chunks)
        )
        end_idx = min(end_idx, len(state.chunks))

        # Create overlapping windows
        windows = _create_overlapping_windows(
            state.chunks,
            start_idx,
            end_idx,
            state.config.window_size,
            state.config.overlap_size,
        )

        logger.info(
            f"Created {len(windows)} overlapping windows for section {section.section_type}"
        )

        # Process each window
        for window_idx, (win_start, win_end) in enumerate(windows):
            # Get chunks for this window
            window_chunks = state.chunks[win_start:win_end]
            window_text = "\n".join(
                [
                    c.content if hasattr(c, "content") else str(c)
                    for c in window_chunks
                ]
            )

            # Extract references from this window
            try:
                result = await reference_extractor.ainvoke(
                    {
                        "full_document": window_text,
                        "supporting_documents": supporting_documents,
                    }
                )

                # Check-before-add: incremental deduplication
                for new_ref in result.references:
                    is_dup, existing_idx = _check_if_duplicate(
                        new_ref, all_references, state.config.fuzzy_threshold
                    )

                    if is_dup:
                        # Merge with existing (keep more complete version)
                        all_references[existing_idx] = _merge_reference_versions(
                            all_references[existing_idx], new_ref
                        )
                        logger.debug(
                            f"Merged duplicate reference at index {existing_idx}"
                        )
                    else:
                        # Add new reference
                        all_references.append(new_ref)
                        logger.debug(
                            f"Added new reference (total: {len(all_references)})"
                        )

            except Exception as e:
                logger.error(
                    f"Error extracting from window {window_idx} "
                    f"(chunks {win_start}-{win_end}): {e}"
                )
                # Continue with other windows

    logger.info(f"Extraction complete: {len(all_references)} unique references extracted")

    return {"references": all_references}

