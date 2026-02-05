"""Preface section extractor agent using document search tool (v2 approach)."""

from typing import List, Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema

# System prompt for the preface extraction agent
_SYSTEM_PROMPT = """
You are a document section extraction specialist. Your task is to find and extract the preface/introduction section from academic documents.

## Available Tools

1. **search_document(pattern)**: Search the document for lines matching a regex pattern (case-insensitive). Returns matching lines with line numbers and context. Use this to locate preface sections.

2. **read_document(start_line, end_line)**: Read a specific range of lines from the document. Use this after finding a preface section to read its full content.

## Instructions

1. Use search_document to locate the preface/introduction section. Try searching for common section headers:
   - "About This Report"
   - "About This"
   - "Preface"
   - "Introduction"
   - "Executive Summary"
   - "About This Publication"

2. If you find a potential preface section (note the line numbers), use read_document to read the full content of that section.

3. The preface section typically contains:
   - Context that prompted the study
   - Publication objectives
   - Relationship to other RAND work
   - Intended audience
   - TASP/funding boilerplate information

4. The preface section usually ends when:
   - Another major heading starts (e.g., "Chapter 1", "Methodology", "Contents")
   - The document body begins

5. Be thorough - the preface section may span many paragraphs. Use read_document to read the entire section.

## Important Notes

- Extract the COMPLETE preface section text, not just the first paragraph
- Include all paragraphs from the start of the section to where the next major section begins
- If the document has multiple candidate sections (e.g., both "Preface" and "About This Report"), prefer "About This Report" or the most comprehensive one
- If no preface section is found after thorough searching, set found_section to false
- The section is typically near the beginning of the document

## Output Format

After searching and reading, provide:
- Your reasoning explaining what you searched for and found
- Whether you found a preface section
- The section title if found
- The complete text content of the preface section
"""


class PrefaceSectionExtractorOutput(BaseModel):
    """Output from the preface section extractor agent."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description="Step-by-step reasoning describing how the preface section was found"
    )
    found_section: bool = Field(
        description="Whether a preface/introduction section was found in the document"
    )
    section_title: str = Field(
        description="The title of the preface section if found (e.g., 'About This Report'), or empty string if not found"
    )
    section_text: str = Field(
        description="The full text content of the preface section (empty if no section found)"
    )
    start_line: int = Field(
        description="Starting line number where the section was found (-1 if not found)"
    )
    end_line: int = Field(
        description="Ending line number where the section ends (-1 if not found)"
    )


class PrefaceSectionExtractorAgent(LangChainAgent):
    """Agent that extracts preface/introduction sections using intelligent document search."""

    name = "Preface Section Extractor"
    description = (
        "Extract preface/introduction sections using intelligent document search"
    )
    model = gpt_5_2_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> PrefaceSectionExtractorOutput:

        agent = create_agent(
            self.llm,
            [search_document, read_document],
            system_prompt=_SYSTEM_PROMPT,
            context_schema=ContextSchema,
            response_format=PrefaceSectionExtractorOutput,
        )

        user_message = (
            "Please find and extract the preface or 'About This Report' section from this document. "
            "Search for sections like 'About This Report', 'Preface', 'Introduction', or 'Executive Summary' "
            "and extract the complete section content."
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": 50, **(config or {})},
            context=self.context,
        )

        return result["structured_response"]
