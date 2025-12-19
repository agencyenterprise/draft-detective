"""Section detection node - detects bibliography/reference sections using AI."""

import logging
import re
from typing import List, Optional

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionState,
    ReferenceSection,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

# Context window size for section detection
CONTEXT_WINDOW_SIZE = 300  # chars
SAMPLE_RATE = 10  # Sample every Nth chunk


class DetectedSectionsResponse(BaseModel):
    """Response from section detection agent."""

    sections: List[ReferenceSection] = Field(
        description="List of detected reference sections"
    )


_section_detector_prompt = ChatPromptTemplate.from_template(
    """
# Task
You are a section detector for academic documents. Given context windows from a document,
identify which ones contain reference/bibliography section markers.

Reference sections can be named:
- "References", "Bibliography", "Works Cited", "Literature Cited"
- "Notes", "Footnotes", "Endnotes" (for footnote-style references)
- "Appendix X: References/Sources" (for appendix references)
- Variations in other languages: "Références", "Bibliografía", etc.

For each context window that contains a section marker, return:
- section_type: "bibliography" | "footnotes" | "appendix_references"
- start_chunk_index: The chunk index where the section starts
- end_chunk_index: None (we'll assume it goes to end or next section)
- confidence: 0-1 score for detection confidence
- section_header: The detected header text

## Context Windows

{context_windows}

## Instructions
- Only return sections that clearly mark beginning of references
- Ignore false positives (e.g., "see references" in body text)
- If no sections found, return empty list
"""
)


class SectionDetectorAgent(LangChainAgent):
    """AI agent for detecting reference sections."""

    name = "Section Detector"
    description = "Detect reference/bibliography sections in documents"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = DetectedSectionsResponse

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> DetectedSectionsResponse:
        messages = _section_detector_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


def _aggregate_chunks_for_detection(
    chunks: List, sample_rate: int = SAMPLE_RATE
) -> List[dict]:
    """
    Aggregate chunks into context windows for section detection.

    Samples every Nth chunk and aggregates with neighbors to create ~300 char contexts.
    """
    context_windows = []

    for i in range(0, len(chunks), sample_rate):
        # Get chunk and neighbors (before + after)
        start_idx = max(0, i - 1)
        end_idx = min(len(chunks), i + 2)

        context_chunks = chunks[start_idx:end_idx]
        combined_text = " ".join(
            [
                c.content if hasattr(c, "content") else str(c)
                for c in context_chunks
            ]
        )

        # Trim to max size
        if len(combined_text) > CONTEXT_WINDOW_SIZE:
            combined_text = combined_text[:CONTEXT_WINDOW_SIZE]

        context_windows.append(
            {
                "text": combined_text,
                "center_chunk_index": i,
                "chunk_indices": list(range(start_idx, end_idx)),
            }
        )

    return context_windows


def _fallback_regex_detection(chunks: List) -> List[ReferenceSection]:
    """
    Fallback regex-based section detection.

    Used if AI detection fails or as a backup.
    """
    sections = []
    patterns = [
        r"^#{1,3}\s*(References?|Bibliography|Works?\s+Cited)",
        r"^(References?|Bibliography):?\s*$",
        r"^#{1,3}\s*\d+\.?\s*(References?|Bibliography)",
    ]

    for i, chunk in enumerate(chunks):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        content_stripped = content.strip()

        for pattern in patterns:
            if re.match(pattern, content_stripped, re.IGNORECASE):
                sections.append(
                    ReferenceSection(
                        section_type="bibliography",
                        start_chunk_index=i,
                        end_chunk_index=None,
                        confidence=0.9,
                        section_header=content_stripped[:50],
                    )
                )
                logger.info(f"Regex detected bibliography section at chunk {i}")
                break

    return sections


@register_node(
    "Detect reference sections",
    "Detect all reference/bibliography sections in document",
)
async def detect_sections(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> ReferenceExtractionState:
    """
    Detect reference sections using AI with regex fallback.

    Creates context windows from sampled chunks and uses AI to identify
    section markers. Falls back to regex if AI fails or finds nothing.
    """
    if not state.chunks:
        logger.warning("No chunks available for section detection")
        return {"detected_sections": []}

    logger.info(f"Detecting reference sections from {len(state.chunks)} chunks")

    # Create context windows for AI detection
    context_windows = _aggregate_chunks_for_detection(state.chunks, SAMPLE_RATE)

    # Format for prompt
    windows_text = "\n\n".join(
        [
            f"Window {i} (center chunk {w['center_chunk_index']}):\n{w['text']}"
            for i, w in enumerate(context_windows)
        ]
    )

    try:
        # Try AI detection first
        detector = SectionDetectorAgent(runtime.context)
        result = await detector.ainvoke({"context_windows": windows_text})

        detected_sections = result.sections

        if detected_sections:
            logger.info(
                f"AI detected {len(detected_sections)} reference sections: "
                f"{[s.section_type for s in detected_sections]}"
            )
            return {"detected_sections": detected_sections}

    except Exception as e:
        logger.warning(f"AI section detection failed: {e}, falling back to regex")

    # Fallback to regex detection
    sections = _fallback_regex_detection(state.chunks)

    if not sections:
        # No sections found - assume last 15% of document contains references
        last_chunk_idx = max(0, len(state.chunks) - int(len(state.chunks) * 0.15))
        sections = [
            ReferenceSection(
                section_type="bibliography",
                start_chunk_index=last_chunk_idx,
                end_chunk_index=None,
                confidence=0.5,
                section_header="Assumed bibliography section (last 15%)",
            )
        ]
        logger.info(
            f"No sections detected, assuming bibliography in last 15% (chunk {last_chunk_idx})"
        )

    return {"detected_sections": sections}

