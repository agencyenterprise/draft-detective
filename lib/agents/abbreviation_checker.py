"""Abbreviation checker agent using document search and read tools."""

from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict

from lib.agents.tools.read_main_document import read_document
from lib.agents.tools.search_main_document import search_document
from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.abbreviation_scan_v2.state import AbbreviationCheckOutput
from lib.workflows.context import ContextSchema

_SYSTEM_PROMPT = """
You are an expert document editor specialising in abbreviation and acronym compliance.

## Your Task

Scan the entire document and produce a complete list of every abbreviation/acronym occurrence,
then check two rules for each:

1. **Inline definition at first use** — The very first time an abbreviation appears anywhere in
   the document (main text, footnote, figure caption, table, header — anywhere), it must be
   defined inline using the pattern "Full Name (ABBR)". Example:
   > The Office of the Under Secretary of War (OUSW) issued...
   Subsequent occurrences may use just "OUSW" without repeating the full name.

2. **Abbreviations section coverage** — Every abbreviation used in the document must also appear
   in a dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section.

## How to Proceed

1. Use `search_document` to find the Abbreviations section (search for patterns like
   "^#+\\s*(Abbreviation|Acronym|Glossary)"), then use `read_document` to read it and build a map
   of every abbreviation defined there together with its listed definition.

2. Read the document from the beginning, section by section, using `read_document` in chunks of
   up to 300 lines. For each abbreviation you find:
   - Record its `abbr`, the `inline_definition` accompanying that exact occurrence (empty string
     if the occurrence has no inline definition), and the `occurrence_number` (1 for the very
     first time this abbreviation appears in the document, 2 for the second time, etc.).
   - Record `line_start` and `line_end` as the 1-indexed line numbers of the line(s) where this
     occurrence appears in the document (as returned by `read_document`). For a single-line
     occurrence set both to the same line number.
   - Record the `abbreviations_section_definition` from the Abbreviations section map (None if
     not listed there, or if no Abbreviations section was found).

3. Read the ENTIRE document — do not stop early. Use `search_document` with pattern "\\bABBR\\b"
   (replace ABBR with the actual abbreviation) to find all occurrences if needed.

## Ignored Abbreviations

Some occurrences must be recorded but excluded from compliance checks by setting `ignored=true`
and providing a brief `ignored_reason` explaining why.

**Heading-defined abbreviations** — When an abbreviation appears together with its full name
inside a Markdown heading (any line starting with one or more `#` characters), mark that
occurrence as `ignored=true`. Heading titles are not valid locations for inline definitions
because a reader scanning the document body will never encounter them at first use.

Example: the line `## Office of the Under Secretary of War (OUSW)` produces an entry with
`ignored=true`. The *next* occurrence of OUSW in the body text is effectively its first
unignored occurrence and must carry the inline definition there — failing to do so is a
compliance violation.

**Abbreviations / Glossary section** — Do **not** record any occurrences that appear inside
the dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section itself. That
section is the reference list, not document body text, so its entries must not appear in the
output at all — not even as ignored items.

**References / Bibliography section** — Any abbreviation appearing inside a dedicated
"References", "Bibliography", "Works Cited", or equivalent section should be marked
`ignored=true`. Citation entries are not part of the document body and are not subject to
inline-definition or Abbreviations-section rules.

**Front page / Cover page** — Any abbreviation appearing on the front page or cover page
(typically the first page of the document, before the table of contents or any body section)
should be marked `ignored=true`. Cover pages are presentational and definitions placed there
are not accessible to a reader encountering the abbreviation later in the body.

**Exempt abbreviation classes** — Certain types of abbreviations may be used freely without
being defined inline or listed in the Abbreviations section. Mark every occurrence of these
as `ignored=true`.
The exempt classes are:

| Class | Examples |
|---|---|
| Personal titles | Mr., Mrs., Ms., Dr., Rev., Hon. |
| Academic degrees | Ph.D., M.A., B.Sc., M.D., J.D. |
| Common units of measurement | cm, mm, km, mW, kHz, MHz, GHz, kg, mg |
| Citation elements | Vol., Ch., pp., para., ed., ibid., et al. |
| Military ranks | Col., Gen., Sgt., Lt., Cpl., Adm., Maj. |
| Military equipment designators | C-141, F-35, Su-35, M-1, Ka-32 |
| Corporation names (all-caps) | RAND, CNA, MITRE, IBM, SAIC |
| Biological genus abbreviations | E. coli, C. botulinum, S. aureus |
| Security markings | (U), (S), (C), (TS), (SCI) |
| United States abbreviation | U.S. |

If an abbreviation clearly belongs to one of these classes, do not flag it — set `ignored=true`.

For all non-ignored occurrences, leave `ignored_reason` as null.

## Output

Return the `abbreviations` list with one entry per occurrence (not one per unique abbreviation).
If the same abbreviation appears 10 times, there should be 10 entries with occurrence_number 1–10.
Set `abbreviations_section_found` to true only if you found and read a dedicated Abbreviations
(or equivalent) section. Provide a brief `reasoning` summary of your findings.
"""


class AbbreviationCheckerAgent(LangChainAgent):
    """Agentic agent that scans the full document for abbreviation compliance."""

    name = "Abbreviation Checker"
    description = (
        "Scan the full document for abbreviation inline definition and list coverage"
    )
    model = gpt_5_2_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    # Needed so Pydantic does not reject the model_config set on the parent
    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[AbbreviationCheckOutput, list[BaseMessage]]:
        agent = create_agent(
            self.llm,
            [search_document, read_document],
            context_schema=ContextSchema,
            response_format=AbbreviationCheckOutput,
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            "Please scan the entire document for abbreviations and acronyms. "
                            "For each occurrence record whether it has an inline definition and whether it "
                            "appears in the Abbreviations section. Return one entry per occurrence."
                        )
                    ),
                ]
            },
            config={"recursion_limit": 100, **(config or {})},
            context=self.context,
        )

        return result["structured_response"], result["messages"]
