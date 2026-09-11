"""Abbreviation checker agent using document search and read tools."""

from typing import List, Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.abbreviation_scan_v2.occurrence_reporting import (
    AbbreviationReporter,
)
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationCheckOutput,
    AbbreviationItem,
)
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent_types import DEEP_AGENT_RECURSION_LIMIT

# The extraction *method* lives in the portable `abbreviation-extraction` skill
# (the single source of truth). This backend-only addendum carries the
# Draft-Detective specifics the skill omits: where the document lives, the
# document-access tools, and the exact structured-output field mapping the
# downstream deterministic checks depend on.
_ENV_GUIDANCE = """\

---

## Environment & output

The document is available at `/main.md` — use the available search and read tools to read or
search it (e.g. search for headings like `^#+\\s*(Abbreviation|Acronym|Glossary)` to locate the
Abbreviations section).

Read it in 200-line chunks — `read_file("/main.md", offset=0, limit=200)`, then `offset=200`,
`offset=400`, and so on. A read returning fewer lines than you asked for means you reached the
end.

A read is capped at ~20,000 tokens; past that it is silently cut off and ends with a truncation
notice, and a larger `limit` will not recover the rest. On that notice, halve the chunk and
retry the same offset, then continue from the last line you actually received rather than the
next round-number offset.

Record the catalogue through the `record_abbreviations` tool — **not** in your final response —
as you finish each chunk, rather than saving it all for the end. A call takes at most 200
occurrences and an oversized batch is rejected whole, so split a dense chunk across several
calls.

Each occurrence records:
- `abbr`: the abbreviation in its singular base form (e.g. "LLM", not "LLMs");
- `inline_definition`: the inline definition accompanying this exact occurrence, or an empty
  string when none accompanies it;
- `occurrence_number`: the 1-based count of how many times this abbreviation has appeared so far
  (1 for the first occurrence);
- `line_start` / `line_end`: the 1-indexed line range in `/main.md` (same line number for a
  single-line occurrence);
- `abbreviations_section_definition`: the definition listed in the Abbreviations section, or
  `None` when the abbreviation is not listed there or no such section exists;
- `ignored`: `true` for occurrences excluded from compliance checks (headings, References /
  Bibliography, cover page, exempt classes), `false` otherwise;
- `ignored_reason`: a brief explanation when `ignored` is `true`, otherwise `None`.

Your final response carries only two fields: set `abbreviations_section_found` to `true` only if
you found and read a dedicated Abbreviations (or equivalent) section, and give a brief
`reasoning` summary stating the document's total line count, the last line you examined, and how
many occurrences you recorded.
"""


class AbbreviationCheckerAgent(LangChainAgent):
    """Agentic agent that scans the full document for abbreviation compliance."""

    name = "Abbreviation Checker"
    description = (
        "Scan the full document for abbreviation inline definition and list coverage"
    )
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[
        AbbreviationCheckOutput, List[AbbreviationItem], list[BaseMessage]
    ]:
        reporter = AbbreviationReporter()
        deep_agent = create_deep_agent(
            model=self.llm,
            tools=reporter.tools,
            context_schema=ContextSchema,
            response_format=AutoStrategy(AbbreviationCheckOutput),
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(),
                "messages": [
                    SystemMessage(
                        content=load_skill_prompt("abbreviation-extraction")
                        + _ENV_GUIDANCE
                    ),
                    HumanMessage(
                        content=(
                            "Please scan the entire document for abbreviations and acronyms. "
                            "For each occurrence record whether it has an inline definition and whether it "
                            "appears in the Abbreviations section. Record every occurrence through the "
                            "`record_abbreviations` tool as you read, in batches of at most 200."
                        )
                    ),
                ],
            },
            # Reading and recording now costs a read/tool cycle per 200-line
            # chunk, so the budget has to scale with document length rather than
            # sit at a fixed 100. Uses the shared deep-agent budget, which was
            # raised for exactly this reason when issue reporting moved to tools.
            config={
                "recursion_limit": DEEP_AGENT_RECURSION_LIMIT,
                **(config or {}),
            },
        )

        return result["structured_response"], reporter.occurrences, result["messages"]
