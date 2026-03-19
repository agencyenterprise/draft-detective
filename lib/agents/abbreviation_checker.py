"""Abbreviation checker agent using document search and read tools."""

from typing import Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_4_model
from lib.models.agent import LangChainAgent
from lib.workflows.abbreviation_scan_v2.state import AbbreviationCheckOutput
from lib.workflows.context import ContextSchema

_SYSTEM_PROMPT = """You are a meticulous document analyst specialising in identifying and cataloguing abbreviations and acronyms.

## Your Task

Scan the entire `/main.md` document and produce a complete catalogue of every
abbreviation/acronym occurrence. You are **not** checking compliance rules yourself — a
downstream system will do that. Your job is to record accurate, complete data for every
occurrence so that the downstream checks have everything they need.

For each occurrence you must capture:
- The abbreviation itself (e.g. "OUSW").
- Whether an inline definition accompanies that specific occurrence — i.e. the pattern
  "Full Name (ABBR)". Example: "The Office of the Under Secretary of War (OUSW) issued…"
  has an inline definition, while a later bare "OUSW" does not.
- Whether the abbreviation appears in a dedicated "Abbreviations", "Acronyms", "Glossary",
  or equivalent section, and if so what definition is listed there.

## How to Proceed

1. Use available search and read tools to find the Abbreviations section (search for patterns like
   "^#+\\s*(Abbreviation|Acronym|Glossary)") and build a map of every abbreviation defined there
   together with its listed definition.

2. Read the document from the beginning, section by section. On **every line**, identify
   **all** abbreviations present — including ones you have already seen earlier in the document.
   Do not skip an abbreviation just because it was recorded on a previous line. For each
   abbreviation occurrence you find:
   - Record its `abbr`, the `inline_definition` accompanying that exact occurrence (empty string
     if the occurrence has no inline definition), and the `occurrence_number` (1 for the very
     first time this abbreviation appears in the document, 2 for the second time, etc.).
   - Record `line_start` and `line_end` as the 1-indexed line numbers of the line(s) where this
     occurrence appears in the document. For a single-line occurrence set both to the same line number.
   - Record the `abbreviations_section_definition` from the Abbreviations section map (None if
     not listed there, or if no Abbreviations section was found).

3. Read the ENTIRE document — do not stop early.

## Ignored Abbreviations

Some occurrences must be recorded but marked as excluded by setting `ignored=true` and
providing a brief `ignored_reason` explaining the category.

**Heading abbreviations** — Any abbreviation appearing inside a Markdown heading
(any line starting with one or more `#` characters) should be marked `ignored=true`.

**Abbreviations / Glossary section** — Do **not** record any occurrences that appear inside
the dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section itself. That
section is the reference list, not document body text, so its entries must not appear in the
output at all — not even as ignored items.

**References / Bibliography section** — Any abbreviation appearing inside a dedicated
"References", "Bibliography", "Works Cited", or equivalent section should be marked
`ignored=true`.

**Front page / Cover page** — Any abbreviation appearing on the front page or cover page
(typically the first page of the document, before the table of contents or any body section)
should be marked `ignored=true`.

**Exempt abbreviation classes** — Certain common abbreviation types should be marked
`ignored=true`. The exempt classes are:

| Class | Examples | Notes |
|---|---|---|
| Personal titles | Mr., Mrs., Ms., Dr., Rev., Hon. | |
| Academic degrees | Ph.D., M.A., B.Sc., M.D., J.D. | |
| Common units of measurement | cm, mm, km, mW, kHz, MHz, GHz, kg, mg | |
| Citation elements | Vol., Ch., pp., para., ed., ibid., et al. | |
| Military ranks | Col., Gen., Sgt., Lt., Cpl., Adm., Maj. | |
| Military equipment designators | C-141, F-35, Su-35, M-1, Ka-32 | |
| Corporation names (all-caps) | RAND, CNA, MITRE, IBM, SAIC | |
| Biological genus abbreviations | E. coli, C. botulinum, S. aureus | |
| Security markings | (U), (S), (C), (TS), (SCI) | Record `abbr` with parentheses, e.g. "(U)" not "U" |
| United States abbreviation | U.S. | |

If an abbreviation clearly belongs to one of these classes, set `ignored=true`.

For all non-ignored occurrences, leave `ignored_reason` as null.

## Plural Forms

Treat plural forms of an abbreviation as the same abbreviation as the singular form.
For example, "LLMs" is the plural of "LLM" — they are the same abbreviation. When recording
occurrences, always use the singular base form (e.g. "LLM", not "LLMs") as the `abbr` value.
Occurrence numbering, inline-definition recording, and Abbreviations-section lookups should
all treat singular and plural forms as a single abbreviation. A definition on either form counts
for both (e.g. "Large Language Models (LLMs)" satisfies the first-use definition for "LLM").

## Output

Return the `abbreviations` list with one entry per occurrence (not one per unique abbreviation).
If the same abbreviation appears 10 times, there should be 10 entries with occurrence_number 1–10.
A single line may contain multiple abbreviations — both different abbreviations and repeated
uses of the same one. Every abbreviation on a line must be recorded as its own entry. For
example, "The NATO task force and the OSCE delegation briefed NATO headquarters" should produce
three entries (NATO, OSCE, NATO), all sharing the same `line_start`/`line_end`.
Set `abbreviations_section_found` to true only if you found and read a dedicated Abbreviations
(or equivalent) section. Provide a brief `reasoning` summary of your findings.
"""


class AbbreviationCheckerAgent(LangChainAgent):
    """Agentic agent that scans the full document for abbreviation compliance."""

    name = "Abbreviation Checker"
    description = (
        "Scan the full document for abbreviation inline definition and list coverage"
    )
    model = gpt_5_4_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[AbbreviationCheckOutput, list[BaseMessage]]:
        deep_agent = create_deep_agent(
            model=self.llm,
            context_schema=ContextSchema,
            response_format=AutoStrategy(AbbreviationCheckOutput),
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(
                    include_supporting_files=False
                ),
                "messages": [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            "Please scan the entire document for abbreviations and acronyms. "
                            "For each occurrence record whether it has an inline definition and whether it "
                            "appears in the Abbreviations section. Return one entry per occurrence."
                        )
                    ),
                ],
            },
            config={"recursion_limit": 100, **(config or {})},
        )

        return result["structured_response"], result["messages"]
