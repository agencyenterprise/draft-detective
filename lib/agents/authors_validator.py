"""Authors validator deep agent for the About This (GER) workflow.

Reads the full document, locates the "About the Authors" section,
and checks each author biography against four publication rules.
Returns structured issues and a markdown summary report.
"""

from typing import Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_4_model
from lib.models.agent import LangChainAgent
from lib.workflows.about_this_ger.state import AgentCheckResult
from lib.workflows.context import ContextSchema

_SYSTEM_PROMPT = """\
You are an expert document reviewer specialising in validating author \
biography sections in research publications.

## Your Task

1. Read `/main.md` and locate the author biography section.
   Common headings include: "About the Authors", "About the Author",
   "Author Biographies", "Author Biography", "Contributors",
   "The Authors", "Author Information", "About the Researcher".
   The section is usually near the beginning or near the end of the document.

2. If no author biography section exists, add a single issue with title
   'No "About the Authors" section found' and a description explaining
   that the document does not contain a recognisable author biography
   section.  Then write a short report noting the absence.
   Do **not** evaluate the rules below — just return that one issue.

3. If you find the section, identify each individual author biography.
   Each biography is typically a separate paragraph about one person.
   Ignore paragraphs shorter than ~50 characters (likely not real bios).

4. For **each** author bio, evaluate it against **every** rule below.
   For each rule that **fails**, add an item to the `issues` list.
   For rules that pass, do **not** create an issue.

## Rules (applied per author)

### Rule 1 — Sentence Count
Each author biography should contain **exactly 3 sentences**.

When counting sentences, be careful with abbreviations that contain
periods — these should NOT be treated as sentence endings:
Ph.D., M.D., J.D., M.S., B.S., M.A., B.A., Dr., Mr., Ms., e.g.,
i.e., etc.

**If wrong count → issue title:** "Author Bio Issue: {author_name}"

### Rule 2 — Position & Affiliation
The biography must mention the author's current **position** (e.g.
senior researcher, policy analyst, professor) and their **institutional
affiliation** (e.g. RAND, a university, a government agency).

**If missing → issue title:** "Author Bio Issue: {author_name}"

### Rule 3 — Research Focus
The biography must describe the author's **research focus**, interests,
or area of expertise.

**If missing → issue title:** "Author Bio Issue: {author_name}"

### Rule 4 — Highest Degree
The biography must mention the author's **highest academic degree**
(e.g. Ph.D., M.A., M.D.).

**If missing → issue title:** "Author Bio Issue: {author_name}"

## Output Requirements

- `issues`: one entry per **failed** rule per author (or a single "section not found"
  entry).  Each entry must have:
  - `title` — "Author Bio Issue: {author_name}" (use the author's full
    name as it appears in the bio).
  - `description` — state which rule failed and briefly explain why.
    If multiple rules fail for the same author, create **one issue per
    failed rule** so each is individually actionable.  Alternatively,
    you may combine all failures for one author into a single issue
    whose description lists every failed rule.
  - `severity` — always "medium".
  - `start_line` — the 1-indexed line number in `/main.md` where the
    text relevant to this issue begins (typically the author's bio paragraph).
  - `end_line` — the 1-indexed line number where that relevant text ends.
- `report_markdown`: a concise markdown report with:
  - A heading naming the section found (or noting its absence).
  - A sub-section per author listing PASS / FAIL for each rule.
  - A summary paragraph with counts (X authors, Y passed all rules,
    Z had issues).

Be thorough but concise.  Do not invent content — base every judgment
strictly on what is present in the document.
"""


class AuthorsValidatorAgent(LangChainAgent):
    """Deep agent that validates author biographies in a document."""

    name = "Authors Validator"
    description = "Validate author biographies against publication rules"
    model = gpt_5_4_model
    temperature = 0.0
    reasoning = {"effort": "medium", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> AgentCheckResult:
        deep_agent = create_deep_agent(
            model=self.llm,
            context_schema=ContextSchema,
            response_format=AutoStrategy(AgentCheckResult),
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(
                    include_supporting_files=False,
                ),
                "messages": [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            "Please read the document and validate every author "
                            "biography against all four rules. "
                            "Return the structured result and a markdown report."
                        )
                    ),
                ],
            },
            config={"recursion_limit": 100, **(config or {})},
        )

        return result["structured_response"]
