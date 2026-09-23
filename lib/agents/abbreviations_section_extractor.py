"""Find and read a document's Abbreviations (or equivalent) section.

A deep agent with the document at `/main.md`: it searches for the section,
reads it, and returns its entries together with where it sits, so the chunked
extraction can leave the section's own lines out of the catalogue.
"""

from typing import List, Optional

from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationSectionEntry,
    AbbreviationsSectionRange,
)
from lib.workflows.context import ContextSchema

# A few searches and a handful of reads for a long section.
RECURSION_LIMIT = 60


class AbbreviationsSectionExtraction(BaseModel):
    sections: List[AbbreviationsSectionRange] = Field(
        default_factory=list,
        description=(
            "Every Abbreviations, Acronyms, or Glossary section found, from its title line to "
            "the last line of its list. Empty when the document has none."
        ),
    )
    entries: List[AbbreviationSectionEntry] = Field(
        default_factory=list,
        description="Every abbreviation listed in those sections, with its definition exactly as written.",
    )


_SYSTEM_PROMPT = """\
The document is at `/main.md`. Find its Abbreviations section (a section titled
"Abbreviations", "Acronyms", "Glossary", or an equivalent, that lists abbreviations with
their definitions) and read its entries.

1. **Locate it.** Search `/main.md` with `grep` for "Abbreviation", "Acronym" and "Glossary",
   with `output_mode="content"`. `grep` matches literal text, not regular expressions, so
   try both capitalised and lower-case forms. The title is usually a Markdown heading
   (`## Abbreviations`), but a converted document may have a bare or bold title line
   instead. A table-of-contents entry, or a sentence that merely mentions abbreviations,
   is not the section.
2. **Read it** with `read_file` (`offset` is the 0-based line offset), from its title to
   where the list ends: the next heading, or where the entries stop. Read a long section in
   several calls rather than one oversized one.
3. **Extract the entries.** Record every abbreviation listed together with its definition,
   both exactly as written (keep capitalisation and punctuation). A glossary entry that
   defines an ordinary term rather than an abbreviation is not an entry.

Report each such section in `sections`, with the 1-indexed line numbers `read_file` shows
for its title and for the last line of its list. Set `lists_abbreviations` to false for a
glossary that defines only ordinary terms. Return no sections when the document has none.
"""


class AbbreviationsSectionExtractorAgent(LangChainAgent):
    name = "Abbreviations Section Extractor"
    description = "Find a document's Abbreviations section and read its entries"
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[AbbreviationsSectionExtraction, List[BaseMessage]]:
        """Expects `markdown`: the whole document. Returns the extraction and
        the agent's full conversation, system prompt included."""
        markdown: str = prompt_kwargs["markdown"]
        total_lines = markdown.count("\n") + 1
        agent = create_deep_agent(
            model=self.llm,
            context_schema=ContextSchema,
            response_format=AutoStrategy(AbbreviationsSectionExtraction),
        )
        messages: List[BaseMessage] = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "Find and read the Abbreviations section of /main.md "
                    f"(the document has {total_lines} lines)."
                )
            ),
        ]
        result = await agent.ainvoke(
            {"files": {"/main.md": create_file_data(markdown)}, "messages": messages},
            config={"recursion_limit": RECURSION_LIMIT, **(config or {})},
        )
        return result["structured_response"], result["messages"]
