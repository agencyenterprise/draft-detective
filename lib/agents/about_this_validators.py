"""Deep agents that validate the About This (GER) sections of a document.

Each agent reads the full document, locates its section (the preface /
introduction, or the "About the Authors" biographies), and checks it against
the rules in its portable skill. It reports issues through tools and writes a
markdown summary report to a file.
"""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.agents.deep_agent_setup import agent_input, build_deep_agent
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.about_this_ger.state import AgentCheckResult
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent import main_document_text
from lib.workflows.simple_deep_agent.agent_types import (
    DEEP_AGENT_RECURSION_LIMIT,
    markdown_result_from_run,
)
from lib.workflows.simple_deep_agent.issue_reporting import (
    IssueReporter,
    collect_deep_agent_run,
)


def _env_guidance(report_issue_rule: str, report_layout: str) -> str:
    """The backend addendum appended to a check's skill.

    The rules live in the portable skill (the source of truth; deployments
    customise it by editing the skill file). This addendum carries the
    Draft-Detective specifics the skill omits: where the document lives and how
    to map findings onto the issues output contract.
    """
    return f"""\

---

## Environment & output

The document is available at `/main.md` — use your tools to read or search it.

Report findings following the conventions in the issues skill (`/skills/issues/SKILL.md`):
- {report_issue_rule};
- make no `report_issue` calls when every rule passes;
- write an overall report to `/report.md` using `write_file`: a heading naming the section found (or noting its absence), {report_layout}.

`/report.md` and the issue tool calls are the deliverables. Nothing in your final message is used in their place.
"""


PREFACE_ENV_GUIDANCE = _env_guidance(
    'call `report_issue` once per failed rule (or for the single "section not found" issue), with the exact title and severity given above',
    "a PASS/FAIL checklist of the six rules with a brief note each, and a summary paragraph",
)

AUTHORS_ENV_GUIDANCE = _env_guidance(
    'call `report_issue` once per failed rule per author (or for the single "section not found" issue), with the title and severity given above',
    "a sub-section per author listing PASS/FAIL for each rule, and a summary paragraph with counts (X authors, Y passed all rules, Z had issues)",
)


class AboutThisValidatorAgent(LangChainAgent):
    """Deep agent that checks one About This section against its skill's rules.

    Subclasses name the skill, the backend addendum and the request that starts
    the run.
    """

    model = gpt_5_6_terra_model
    reasoning = {"effort": "medium", "summary": "auto"}
    skill: str
    env_guidance: str
    request: str

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig | None = None,
    ) -> tuple[AgentCheckResult, list[BaseMessage]]:
        """Return the check result and the agent's full conversation, system prompt included."""
        files = await self.context.file_artifacts_service.get_deepagent_backend_files()
        # The document is what the agent's passages are checked against.
        issue_reporter = IssueReporter(document_text=main_document_text(files))
        deep_agent = build_deep_agent(
            model=self.llm,
            tools=issue_reporter.tools,
            context_schema=ContextSchema,
        )

        result = await deep_agent.ainvoke(
            agent_input(
                files=files,
                messages=[
                    SystemMessage(
                        content=load_skill_prompt(self.skill) + self.env_guidance
                    ),
                    HumanMessage(content=self.request),
                ],
            ),
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


class PrefaceValidatorAgent(AboutThisValidatorAgent):
    """Deep agent that validates the preface section of a document."""

    name = "Preface Validator"
    description = (
        "Validate the preface / introduction section against publication rules"
    )
    skill = "about-this-preface"
    env_guidance = PREFACE_ENV_GUIDANCE
    request = (
        "Please read the document and validate the preface / "
        "introduction section against all six rules. Deliver "
        "issues through the tools and the report through the file."
    )


class AuthorsValidatorAgent(AboutThisValidatorAgent):
    """Deep agent that validates author biographies in a document."""

    name = "Authors Validator"
    description = "Validate author biographies against publication rules"
    skill = "about-this-authors"
    env_guidance = AUTHORS_ENV_GUIDANCE
    request = (
        "Please read the document and validate every author "
        "biography against all four rules. Deliver issues "
        "through the tools and the report through the file."
    )
