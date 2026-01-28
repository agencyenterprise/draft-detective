"""Reference extractor v2 agent using document search tool."""

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


class ReferenceExtractorV2Output(BaseModel):
    """Output from the reference extractor agent."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description="Step-by-step reasoning describing how references were found and extracted"
    )
    references: List[str] = Field(
        description="List of extracted bibliographic references from the document"
    )


_system_prompt = PromptTemplate.from_template(
    """
You are a reference extraction specialist. Your task is to find and extract all bibliographic references from the Reference List section of an academic document.

## Available Tools

1. **search_document(pattern)**: Search the document for lines matching a regex pattern (case-insensitive). Returns matching lines with line numbers and context. Use this to locate reference sections.

2. **read_document(start_line, end_line)**: Read a specific range of lines from the document. Use this after finding a reference section to read its full content.

## Instructions

1. Use search_document to locate reference/bibliography sections. Try searching for common section headers like "References", Bibliography", "Works Cited", "Literature Cited", "Sources" etc. It's possible that the reference section is not labeled, so you may need to search for common patterns in the document.

2. Once you find a reference section (note the line numbers), use read_document to read the full content of that section.

3. Extract each individual reference as a complete bibliographic entry. Keep each reference as a single string, preserving the original formatting.

4. Common reference patterns to look for:
   - APA, MLA, Chicago, or other Reference List formats

5. Be thorough - the reference section may span many lines. Use read_document to read larger sections when needed.

## Output Format

After searching and reading, provide:
- Your reasoning explaining what you searched for and found
- A complete list of all extracted references

## Important Notes

- Each reference should be a complete bibliographic entry
- Do not include in-text citations - only extract the full reference entries from the bibliography section
- If no reference section is found, return an empty list
- Footnotes might appear in the end of document with the format "160. Text content here #footnote-ref-160"; they should be ignored as they are not part of the reference list
- Preserve the original text of each reference exactly as it appears, except for the following:
    - Remove entry numbers (e.g., [1], 1., (1)) from the beginning of the reference text
    - If you see a placeholder for repeated authors at the start of a reference (commonly `---.` but also `———.`, `___`, or similar patterns), replace it with the author from the previous reference
    - If a single reference item is split across multiple lines, merge them into a single line (remove line breaks)
"""
)


class ReferenceExtractorV2Agent(LangChainAgent):
    """Agent that extracts references using document search tool."""

    name = "Reference Extractor v2"
    description = "Extract bibliographic references using intelligent document search"
    model = gpt_5_2_model
    temperature = 0.0
    output_schema = ReferenceExtractorV2Output

    def create_llm(self):
        return init_chat_model(
            self.model.model_name,
            temperature=self.temperature,
            timeout=self.timeout,
            api_key=self.context.openai_api_key,
            reasoning={"effort": "low", "summary": "auto"},
        )

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ReferenceExtractorV2Output:
        system_prompt = _system_prompt.invoke({})

        agent = create_agent(
            self.llm,
            [search_document, read_document],
            context_schema=ContextSchema,
            system_prompt=system_prompt.text,
            response_format=self.output_schema,
        )

        user_message = (
            f"""Please extract all bibliographic references from the document."""
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": 50, **(config or {})},
            context=self.context,
        )

        return result["structured_response"]

        # async for chunk in agent.astream(
        #     {"messages": [{"role": "user", "content": user_message}]},
        #     config={"recursion_limit": 50, **(config or {})},
        #     context=self.context,
        #     stream_mode="updates",
        # ):
        #     for step, data in chunk.items():
        #         print(f"step: {step}")
        #         print(f"content: {data['messages'][-1].content_blocks}")

        # return data["structured_response"]
