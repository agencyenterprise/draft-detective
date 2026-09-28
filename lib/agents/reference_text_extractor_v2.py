"""Reference extractor v2 agent using document search tool."""

from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.agents.tools.read_main_document import read_document
from lib.agents.tools.search_main_document import search_document
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.context import ContextSchema


class ExtractedReferenceWithLines(BaseModel):
    """A single reference with its location in the document."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="The complete bibliographic reference text")
    start_line: int = Field(
        description="1-indexed starting line number where this reference begins"
    )
    end_line: int = Field(
        description="1-indexed ending line number where this reference ends"
    )


class ReferenceExtractorV2Output(BaseModel):
    """Output from the reference extractor agent."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description="Step-by-step reasoning describing how references were found and extracted"
    )
    references: List[ExtractedReferenceWithLines] = Field(
        description="List of extracted bibliographic references with their line locations"
    )


# The reference-extraction *procedure* is the portable `reference-extraction`
# skill (the single source of truth). This backend-only addendum carries the
# Draft-Detective specifics the skill omits: the document-access tools and the
# line-range output contract that downstream consumers depend on.
_ENV_GUIDANCE = """\

---

## Tools and output in this environment

You have these tools to read the document:
- `search_document(pattern)`: search for lines matching a regex pattern (case-insensitive); returns matching lines with their line numbers and context. Use it to locate the reference section.
- `read_document(start_line, end_line)`: read a specific range of lines; output is `LINE_NUMBER|content` per line. Use it to read the full section once located.

Begin your output with brief `reasoning` describing what you searched for and found.

For each extracted reference, also report the 1-indexed `start_line` and `end_line` where it appears in the document (from the `read_document` line numbers). If a reference spans multiple lines, use the first line as `start_line` and the last as `end_line`. For example, if `read_document` shows:
```
152|Smith, J. (2020). Title of Paper. Journal, 5(2), 123-145.
153|Doe, A. (2019). Another Paper Title. Publisher.
```
you would output text="Smith, J. (2020). Title of Paper. Journal, 5(2), 123-145." with start_line=152, end_line=152, and text="Doe, A. (2019). Another Paper Title. Publisher." with start_line=153, end_line=153.
"""

_USER_MESSAGE = "Please extract all bibliographic references from the document."


class ReferenceExtractorV2Agent(LangChainAgent):
    """Agent that extracts references using document search tool."""

    name = "Reference Extractor v2"
    description = "Extract bibliographic references using intelligent document search"
    model = gpt_5_6_terra_model
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[ReferenceExtractorV2Output, list[BaseMessage]]:
        agent = create_agent(
            self.llm,
            [search_document, read_document],
            context_schema=ContextSchema,
            response_format=ReferenceExtractorV2Output,
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(
                        content=load_skill_prompt("reference-extraction")
                        + _ENV_GUIDANCE
                    ),
                    HumanMessage(content=_USER_MESSAGE),
                ]
            },
            config={"recursion_limit": 50, **(config or {})},
            context=self.context,
        )

        return result["structured_response"], result["messages"]
