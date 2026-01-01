"""Section detection utilities for reference extraction.

Simple approach:
1. Extract all markdown headings (lines starting with #)
2. Use LLM to identify which one(s) are reference sections
"""

import re
from typing import List

from pydantic import BaseModel, Field

from lib.agents.section_classifier import SectionClassifierAgent
from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction.state import ReferenceSection

# Heading pattern: 1-6 # characters followed by space and then the heading text
# Example: "# Introduction", "## Methods and Results", ..., "###### References".
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


class HeadingInfo(BaseModel):
    """Information about a markdown heading."""

    text: str = Field(description="The heading text")
    level: int = Field(description="Heading level (1-6)")
    start_offset: int = Field(description="Character offset where heading starts")
    end_offset: int = Field(description="Character offset where section ends")


def extract_headings(markdown: str) -> List[HeadingInfo]:
    """
    Extract all markdown headings with their positions.

    Args:
        markdown: Full document markdown text

    Returns:
        List of HeadingInfo with text and character offsets
    """
    if not markdown:
        return []

    headings: List[HeadingInfo] = []
    current_offset = 0

    for line in markdown.split("\n"):
        match = HEADING_PATTERN.match(line)
        if match:
            headings.append(
                HeadingInfo(
                    text=match.group(2).strip(),
                    level=len(match.group(1)),
                    start_offset=current_offset,
                    end_offset=0,
                )
            )
        current_offset += len(line) + 1

    for i, heading in enumerate(headings):
        heading.end_offset = (
            headings[i + 1].start_offset if i + 1 < len(headings) else len(markdown)
        )

    return headings


def _group_consecutive_indices(indices: List[int]) -> List[List[int]]:
    """Group consecutive indices into lists (e.g., [1,2,5,6,7] -> [[1,2], [5,6,7]])."""
    if not indices:
        return []

    sorted_indices = sorted(set(indices))
    groups: List[List[int]] = [[sorted_indices[0]]]

    for idx in sorted_indices[1:]:
        if idx == groups[-1][-1] + 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])

    return groups


async def detect_sections(
    markdown: str, context: ContextSchema
) -> List[ReferenceSection]:
    """
    Detect reference sections using LLM classification.

    Consecutive reference indices are merged into a single section.
    This handles cases where artifacts (like URLs) appear as headings within reference sections.

    Args:
        markdown: Full document markdown text
        context: Workflow context with API keys

    Returns:
        List of detected reference sections
    """
    if not markdown:
        return []

    headings = extract_headings(markdown)
    if not headings:
        return []

    agent = SectionClassifierAgent(context)
    headings_list = "\n".join(f"{i}: {h.text}" for i, h in enumerate(headings))
    result = await agent.ainvoke({"headings_list": headings_list})

    valid_indices = [idx for idx in result.indices if 0 <= idx < len(headings)]
    groups = _group_consecutive_indices(valid_indices)

    sections: List[ReferenceSection] = []
    ref_indices_set = set(valid_indices)

    for group in groups:
        start_idx = group[0]
        last_idx = group[-1]

        # We need to find next heading that is NOT part of reference sections to get the correct end offset
        end_offset = len(markdown)
        for i in range(last_idx + 1, len(headings)):
            if i not in ref_indices_set:
                end_offset = headings[i].start_offset
                break

        sections.append(
            ReferenceSection(
                start_offset=headings[start_idx].start_offset,
                end_offset=end_offset,
            )
        )

    return sections
