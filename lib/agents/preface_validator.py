"""Preface validator deep agent for the About This (GER) workflow.

Reads the full document, locates the preface / introduction section,
and checks it against six publication requirements. Reports issues through
tools and writes a markdown summary report to a file.
"""

from typing import List, Optional

from deepagents import create_deep_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.about_this_ger.state import AgentCheckResult
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent_types import (
    DEEP_AGENT_RECURSION_LIMIT,
    markdown_result_from_run,
)
from lib.workflows.simple_deep_agent.issue_reporting import (
    IssueReporter,
    collect_deep_agent_run,
)

# The preface rules live in the portable `about-this-preface` skill (the source
# of truth; deployments customise it by editing the skill file). This backend
# addendum carries the Draft-Detective specifics the skill omits: where the
# document lives and how to map findings onto the issues output contract.
_ENV_GUIDANCE = """\

---

## Environment & output

The document is available at `/main.md` — use your tools to read or search it.

Report findings following the conventions in the issues skill (`/skills/issues/SKILL.md`):
- call `report_issue` once per failed rule (or for the single "section not found" issue), with the exact title and severity given above;
- make no `report_issue` calls when every rule passes;
- write an overall report to `/report.md` using `write_file`: a heading naming the section found (or noting its absence), a PASS/FAIL checklist of the six rules with a brief note each, and a summary paragraph.

`/report.md` and the issue tool calls are the deliverables. Nothing in your final message is used in their place.
"""


class PrefaceValidatorAgent(LangChainAgent):
    """Deep agent that validates the preface section of a document."""

    name = "Preface Validator"
    description = (
        "Validate the preface / introduction section against publication rules"
    )
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "medium", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[AgentCheckResult, List[BaseMessage]]:
        """Return the check result and the agent's full conversation, system prompt included."""
        issue_reporter = IssueReporter()
        deep_agent = create_deep_agent(
            model=self.llm,
            tools=issue_reporter.tools,
            context_schema=ContextSchema,
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(),
                "messages": [
                    SystemMessage(
                        content=load_skill_prompt("about-this-preface") + _ENV_GUIDANCE
                    ),
                    HumanMessage(
                        content=(
                            "Please read the document and validate the preface / "
                            "introduction section against all six rules. Deliver "
                            "issues through the tools and the report through the file."
                        )
                    ),
                ],
            },
            config={"recursion_limit": DEEP_AGENT_RECURSION_LIMIT, **(config or {})},
        )

        state_result = markdown_result_from_run(
            collect_deep_agent_run(result, issue_reporter)
        )
        check = AgentCheckResult(
            issues=state_result.issues,
            report_markdown=state_result.report_markdown,
        )
        return check, result["messages"]
