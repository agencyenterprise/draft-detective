"""Footnote extraction agent for extracting structured footnotes from text."""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.models.footnote_item import FootnoteItem


class FootnoteExtractorResponse(BaseModel):
    """Response from footnote extraction."""

    footnotes: List[FootnoteItem] = Field(
        default_factory=list,
        description="List of extracted footnotes with marker, text, and reference_code",
    )


_footnote_extractor_prompt = ChatPromptTemplate.from_template(
    """Extract all footnotes from the FOOTNOTE SECTION text.

FOOTNOTE SECTION TEXT:
```
{text}
```

Rules:
- Extract footnotes that follow patterns like: "160. Text content here #footnote-ref-161"
- For each footnote, extract:
  * marker: The footnote number (e.g., "160", "1", "107")
  * text: The full text content of the footnote
  * reference_code: The anchor reference if present (e.g., "#footnote-ref-161")

- Footnotes may span multiple lines - merge them into single entries
- Remove the marker number and reference code from the text field
- Handle various formats: "N. Text", "[N] Text", "^N Text"
- Reference codes are typically at the end: "#footnote-ref-N"
- If no reference code is present, set it to null

Extract ALL footnotes even if they look similar - do not deduplicate.
"""
)


class FootnoteExtractorAgent(LangChainAgent):
    """Agent to extract structured footnotes from text."""

    name = "Footnote Extractor"
    description = "Extract structured footnotes from document text"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = FootnoteExtractorResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> FootnoteExtractorResponse:
        messages = _footnote_extractor_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


if __name__ == "__main__":
    """Test footnote extraction on EnergyConsiderations.docx."""
    import asyncio
    import os

    from lib.workflows.footnote_extraction.utils.section_detector import (
        detect_footnote_region,
    )
    from lib.workflows.context import ContextSchema

    async def test_footnote_extraction():
        """Test footnote extraction on EnergyConsiderations.docx."""

        # Path to the test document (processed markdown)
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../rand-personal/2026-jan-energy-considerations-package/EnergyConsiderations_processed.md",
        )

        print(f"Testing with file: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print()

        # Read markdown file
        print("Reading markdown file...")
        with open(file_path, "r") as f:
            markdown = f.read()

        print(f"Markdown length: {len(markdown)} characters")
        print()

        # Show end of document to see footnote format
        print("=" * 80)
        print("LAST 2000 CHARACTERS OF DOCUMENT:")
        print("=" * 80)
        print(markdown[-2000:])
        print()

        # Test pattern-based detection
        print("=" * 80)
        print("TESTING PATTERN-BASED DETECTION:")
        print("=" * 80)
        sections = detect_footnote_region(markdown)

        if sections:
            print(f"✓ Detected {len(sections)} footnote section(s)")
            for i, section in enumerate(sections):
                print(f"\nSection {i+1}:")
                print(f"  Start offset: {section.start_offset}")
                print(f"  End offset: {section.end_offset}")
                print(f"  Length: {section.end_offset - section.start_offset} chars")

                # Extract section text
                section_text = markdown[section.start_offset : section.end_offset]

                # Show first 1000 chars of footnote section
                print(f"\n  First 1000 chars of footnote section:")
                print("  " + "-" * 76)
                print("  " + section_text[:1000].replace("\n", "\n  "))
                print("  " + "-" * 76)

                # Count footnotes (rough estimate by counting line starts with numbers)
                lines = section_text.split("\n")
                footnote_lines = [
                    line
                    for line in lines
                    if line.strip() and line.strip()[0].isdigit()
                ]
                print(f"\n  Estimated footnote count: {len(footnote_lines)}")

                # Show first few footnote entries
                print(f"\n  First 5 footnote entries:")
                for j, line in enumerate(footnote_lines[:5]):
                    print(f"    {j+1}. {line[:100]}...")

                # Test LLM extraction on first 5000 chars
                print("\n" + "=" * 80)
                print("TESTING LLM EXTRACTION (first 5000 chars):")
                print("=" * 80)

                test_text = section_text[:5000]
                context = ContextSchema()
                agent = FootnoteExtractorAgent(context)

                result = await agent.ainvoke({"text": test_text})

                print(f"\n✓ Extracted {len(result.footnotes)} footnotes")
                print("\nFirst 3 extracted footnotes:")
                for j, footnote in enumerate(result.footnotes[:3]):
                    print(f"\n  Footnote {j+1}:")
                    print(f"    Marker: {footnote.marker}")
                    print(f"    Text: {footnote.text[:150]}...")
                    print(f"    Reference code: {footnote.reference_code}")

        else:
            print("✗ No footnote sections detected")
            print("\nLast 20 lines of document:")
            lines = markdown.split("\n")
            for line in lines[-20:]:
                print(f"  {line}")

    asyncio.run(test_footnote_extraction())
