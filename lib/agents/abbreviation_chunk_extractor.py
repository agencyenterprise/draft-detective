"""Catalogue the abbreviation occurrences in one line range of a document.

One deep agent per chunk. It gets the whole document at `/main.md` but answers
only for its assigned lines, so a long document costs more agents rather than
one agent whose conversation grows until it overflows.
"""

from typing import List, Optional

from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langchain.agents.structured_output import AutoStrategy, StructuredOutputError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.agents.structured_output_salvage import ai_message_text, salvage_models
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    ChunkExtractionResult,
    ChunkOccurrence,
)
from lib.workflows.context import ContextSchema

# Reading the range is one or two tool calls, looking up which section it sits
# in a couple more; this leaves room for retries without letting a confused
# agent wander for long.
RECURSION_LIMIT = 40

# The extraction *method* lives in the portable `abbreviation-extraction`
# skill. This addendum carries the Draft-Detective specifics: where the
# document is, how to read an assigned range, and the output fields. It is
# static so the system prompt stays a cacheable prefix; the range goes in the
# user message.
CHUNK_GUIDANCE = """\


---

## Environment & output

The document is at `/main.md`. You are responsible for **one line range** of it, given in
the message. The other ranges are catalogued separately and the results are combined
afterwards. So:

- Read your range with `read_file`. `offset` is the 0-based line offset, so lines X-Y are
  `read_file("/main.md", offset=X-1, limit=Y-X+1)`. Lines longer than 5,000 characters come
  back split into continuation lines (e.g. `12.1`, `12.2`) that count toward the limit; keep
  reading until you have seen your last line.
- Catalogue every occurrence on the lines of your range, and only those: every abbreviation
  on every line, including repeats of the same abbreviation. You may read outside your range
  for context, but never record an occurrence from outside it.
- Do **not** count occurrences and do **not** look up the Abbreviations section. Both are
  computed after the ranges are combined; record each occurrence exactly as it appears.
- Your range may fall on the cover page, inside the References / Bibliography section, among
  footnotes or endnotes, or inside the Abbreviations section itself, and the rules above
  treat each of those differently. When your range does not show where it sits (for example, it starts in the
  middle of a section), find out before recording: read the lines just before it, or list the
  document's headings with `grep(pattern="#", path="/main.md", output_mode="content")`.
  `grep` matches literal text, not regular expressions.

Return `occurrences`, one entry per occurrence in reading order, each with:
- `abbr`: the abbreviation in its singular base form (e.g. "LLM", not "LLMs");
- `inline_definition`: the inline definition accompanying this exact occurrence, or an
  empty string when none accompanies it;
- `line_start` / `line_end`: the 1-indexed line range in `/main.md`, as numbered by
  `read_file` (equal for a single line);
- `ignored`: `true` for occurrences excluded from compliance checks, `false` otherwise;
- `ignored_reason`: a brief explanation when `ignored` is `true`, otherwise `null`.

Return an empty list when your range contains no abbreviations.
"""

_RANGE_MESSAGE = (
    "Catalogue the abbreviations on lines {start_line}-{end_line} of /main.md "
    "(the document has {total_lines} lines)."
)


class PartialChunkExtractionError(Exception):
    """The response was cut off, but complete occurrences were recovered."""

    def __init__(self, result: ChunkExtractionResult, messages: List[BaseMessage]) -> None:
        self.result = result
        self.messages = messages
        super().__init__(
            f"Chunk extraction output was truncated; recovered "
            f"{len(result.occurrences)} complete occurrence(s) before the cut."
        )


class AbbreviationChunkExtractorAgent(LangChainAgent):
    """Extract the abbreviation occurrences on one line range of /main.md."""

    name = "Abbreviation Chunk Extractor"
    description = "Catalogue every abbreviation occurrence in one line range of a document"
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[ChunkExtractionResult, List[BaseMessage]]:
        """Expects `markdown` (the whole document), `start_line` and `end_line`."""
        agent = create_deep_agent(
            model=self.llm,
            context_schema=ContextSchema,
            response_format=AutoStrategy(ChunkExtractionResult),
        )
        messages = build_messages(prompt_kwargs)
        try:
            result = await agent.ainvoke(
                {
                    "files": {"/main.md": create_file_data(prompt_kwargs["markdown"])},
                    "messages": messages,
                },
                config={"recursion_limit": RECURSION_LIMIT, **(config or {})},
            )
        except StructuredOutputError as e:
            salvaged = _salvage(e)
            if not salvaged:
                raise
            # The intermediate tool calls are lost with the exception; keep the
            # prompt and the truncated answer so the chunk can still be traced.
            raise PartialChunkExtractionError(
                ChunkExtractionResult(occurrences=salvaged), [*messages, e.ai_message]
            ) from e

        return result["structured_response"], result["messages"]


def build_messages(prompt_kwargs: dict) -> List[BaseMessage]:
    total_lines = prompt_kwargs["markdown"].count("\n") + 1
    return [
        SystemMessage(content=load_skill_prompt("abbreviation-extraction") + CHUNK_GUIDANCE),
        HumanMessage(
            content=_RANGE_MESSAGE.format(
                start_line=prompt_kwargs["start_line"],
                end_line=prompt_kwargs["end_line"],
                total_lines=total_lines,
            )
        ),
    ]


def _salvage(error: StructuredOutputError) -> List[ChunkOccurrence]:
    ai_message = getattr(error, "ai_message", None)
    if not isinstance(ai_message, AIMessage):
        return []
    return salvage_models(ai_message_text(ai_message), "occurrences", ChunkOccurrence)

