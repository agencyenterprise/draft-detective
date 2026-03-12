"""Preface validator deep agent for the About This (GER) workflow.

Reads the full document, locates the preface / introduction section,
and checks it against six publication requirements.  Returns structured
issues and a markdown summary report.
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
You are an expert document reviewer specialising in validating the preface \
or introductory section of research publications.

## Your Task

1. Read `/main.md` and locate the preface / introduction section.
   Common headings include: "About This Report", "About This", "Preface",
   "Introduction", "Executive Summary", "About This Publication".
   The section is usually near the beginning of the document, before the
   main body chapters.

2. If no preface section exists, add a single issue with title
   "No preface section found" and a description explaining that the
   document does not contain a recognisable preface / introduction
   section.  Then write a short report noting the absence.
   Do **not** evaluate the rules below — just return that one issue.

3. If you find the section, evaluate it against **every** rule below.
   For each rule that **fails**, add an item to the `issues` list.
   For rules that pass, do **not** create an issue.

## Rules

### Rule 1 — Establishes Context
Does the section explain **why** this work was undertaken?
Look for sentences that establish the context or motivation that prompted
the study.  The section should give the reader a clear sense of the
problem, gap, or situation that led to this research.

**If missing → issue title:** "Preface: Establishes Context Missing"

### Rule 2 — Explains Objectives
Does the section state **what** the publication aims to achieve?
Look for explicit statements of goals, objectives, or research questions
the work sets out to address.

**If missing → issue title:** "Preface: Explains Objectives Missing"

### Rule 3 — Identifies Audience
Does the section specify **who** this publication is for?
Look for sentences that name or describe the intended readership
(e.g. policymakers, analysts, researchers in a specific field).

**If missing → issue title:** "Preface: Identifies Audience Missing"

### Rule 4 — Situates Within Literature
Does the section explain **how** this work relates to existing research?
Look for references to prior work, related studies, or the broader
research landscape.  The section should position this publication within
its field.

**If missing → issue title:** "Preface: Situates Within Literature Missing"

### Rule 5 — States Contribution
Does the section articulate the paper's **novel contribution**?
Look for statements about new findings, unique methods, insights, or
advances over existing work that this publication provides.

**If missing → issue title:** "Preface: States Contribution Missing"

### Rule 6 — Defines Scope
Does the section define what is and what is **not** covered?
Look for statements about the study's boundaries, limitations, or
explicit inclusions / exclusions.

**If missing → issue title:** "Preface: Defines Scope Missing"

## Output Requirements

- `issues`: one entry per **failed** rule (or a single "section not found" entry).  Each entry must have:
  - `title` — use the exact title specified above.
  - `description` — a 1-3 sentence explanation of why the rule failed,
    referencing what was looked for and what was (or was not) found.
  - `severity` — always "medium".
  - `start_line` — the 1-indexed line number in `/main.md` where the
    text relevant to this issue begins.
  - `end_line` — the 1-indexed line number where that relevant text ends.
- `report_markdown`: a concise markdown report with:
  - A heading naming the section found (or noting its absence).
  - A checklist of all six rules with PASS / FAIL and a brief note.
  - A summary paragraph.

Be thorough but concise.  Do not invent content — base every judgment
strictly on what is present in the document.
"""


class PrefaceValidatorAgent(LangChainAgent):
    """Deep agent that validates the preface section of a document."""

    name = "Preface Validator"
    description = (
        "Validate the preface / introduction section against publication rules"
    )
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
                            "Please read the document and validate the preface / "
                            "introduction section against all six rules. "
                            "Return the structured result and a markdown report."
                        )
                    ),
                ],
            },
            config={"recursion_limit": 100, **(config or {})},
        )

        return result["structured_response"]
