"""Author bio extractor agent using document search tool (v2 approach)."""

from typing import List, Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class AuthorBio(BaseModel):
    """A single author biography extracted from the document."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The author's full name")
    bio_text: str = Field(description="The complete biography text for this author")
    start_line: int = Field(description="Starting line number where this bio was found")
    end_line: int = Field(description="Ending line number where this bio ends")


class AuthorBioExtractorOutput(BaseModel):
    """Output from the author bio extractor agent."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description="Step-by-step reasoning describing how author bios were found"
    )
    found_section: bool = Field(
        description="Whether an 'About the Authors' section was found in the document"
    )
    section_title: str = Field(
        description="The title of the author bio section if found (e.g., 'About the Authors', 'Contributors'), or empty string if not found"
    )
    author_bios: List[AuthorBio] = Field(
        description="List of extracted author biographies (empty if no section found)"
    )


_system_prompt = PromptTemplate.from_template(
    """
You are an author biography extraction specialist. Your task is to find and extract author biographies from academic documents.

## Available Tools

1. **search_document(pattern)**: Search the document for lines matching a regex pattern (case-insensitive). Returns matching lines with line numbers and context. Use this to locate author sections.

2. **read_document(start_line, end_line)**: Read a specific range of lines from the document. Use this after finding an author section to read its full content.

## Instructions

1. Use search_document to locate author biography sections. Try searching for common section headers:
   - "About the Author" / "About the Authors"
   - "Author Biographies" / "Author Biography"
   - "Contributors"
   - "The Authors"
   - "Author Information"
   - "About the Researcher"
   - "Author Notes"
   - "Biographical"

2. If you find a potential author section (note the line numbers), use read_document to read the full content of that section.

3. Extract each individual author biography as a complete entry. Each biography typically includes:
   - Author name
   - Position and affiliation (e.g., "senior researcher at RAND")
   - Research focus or interests
   - Academic credentials/degrees

4. Author bios are typically 2-5 sentences each and appear as separate paragraphs.

5. Be thorough - the author section may span many lines. Use read_document to read larger sections when needed.

## Important Notes

- Each author bio should be a complete paragraph about one person
- Do not include acknowledgments or funding information - only extract author biographical paragraphs
- If no author biography section is found after thorough searching, set found_section to false
- The section might be near the end of the document (common placement) or at the beginning
- Some documents may not have an author biography section at all

## Output Format

After searching and reading, provide:
- Your reasoning explaining what you searched for and found
- Whether you found an author biography section
- The section title if found
- A list of all extracted author biographies with their names and full bio text
"""
)


class AuthorBioExtractorAgent(LangChainAgent):
    """Agent that extracts author biographies using intelligent document search."""

    name = "Author Bio Extractor"
    description = "Extract author biographies using intelligent document search"
    model = gpt_5_2_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> AuthorBioExtractorOutput:
        system_prompt = _system_prompt.invoke({})

        agent = create_agent(
            self.llm,
            [search_document, read_document],
            system_prompt=system_prompt.text,
            context_schema=ContextSchema,
            response_format=AuthorBioExtractorOutput,
        )

        user_message = (
            "Please find and extract all author biographies from this document. "
            "Search for an 'About the Authors' section or similar, and extract each individual author's biography."
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": 50, **(config or {})},
            context=self.context,
        )

        return result["structured_response"]
