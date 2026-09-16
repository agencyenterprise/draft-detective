"""Generic deep agent for simple single-node workflows.

The default system prompt defines a generic document-reviewer role.
Callers supply the user prompt (specific rules/criteria) and may optionally
override the system prompt when the default is not appropriate.
"""

from typing import Any, Callable, Literal, Optional, Sequence, Union

from deepagents import create_deep_agent
from deepagents.backends.utils import file_data_to_string
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from lib.agents.tools.view_image import VIEW_IMAGE_PROMPT, view_image
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent, ReasoningDict
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent_types import (
    DEEP_AGENT_RECURSION_LIMIT,
    MAIN_DOCUMENT_PATH,
    DeepAgentRun,
)
from lib.workflows.simple_deep_agent.issue_reporting import (
    IssueReporter,
    collect_deep_agent_run,
)

_SYSTEM_PROMPT = """\
You are a specialist document reviewer. Your task is to review a document \
against rules or criteria provided in the user message and report any issues found.

## Document

The document is available at `/main.md`. Use your tools to read or search its \
content as needed to evaluate the rules given by the user.

## Reporting Issues

Call `report_issue` once for each finding the workflow criteria require, \
following the conventions defined in the issues skill \
(`/skills/issues/SKILL.md`). Do not call it for rules that pass unless the \
workflow criteria explicitly request informational issues with severity `none`. \
If nothing qualifies for reporting, make no `report_issue` calls.

## Report

Write the overall review to `/report.md` using `write_file`. This file is the \
report deliverable: the workflow reads it from the filesystem when you finish, \
and nothing in your final message is used in its place. Write the whole report, \
and if you revise it, write it again in full.\
"""


def _main_document_text(files: dict[str, Any]) -> Optional[str]:
    """Read the document under review out of the DeepAgent backend file tree."""
    file_data = files.get(MAIN_DOCUMENT_PATH)
    if file_data is None:
        return None
    return file_data_to_string(file_data)


class SimpleDeepAgent(LangChainAgent):
    """Deep agent that runs a single validation pass.

    Defaults to a generic document-reviewer system prompt; pass `system_prompt`
    to override it. The user prompt contains the specific rules to check.

    `view_images` binds the `view_image` tool and appends its instructions to
    the system prompt, whichever prompt is in use. It is opt-in: a bound tool
    is an invitation, and a language or structure check would spend turns
    looking at logos. Workflows whose judgment can hinge on a figure ask for it.
    """

    name = "Simple Deep Agent"
    description = "Runs a deep-agent validation pass and records issues through tools"
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "medium", "summary": "auto"}

    def __init__(
        self,
        context: ContextSchema,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        report_issues: bool = True,
        propose_edits: bool = False,
        tools: Optional[Sequence[Union[BaseTool, Callable, dict[str, Any]]]] = None,
        reasoning_effort: Optional[Literal["low", "medium", "high"]] = None,
        timeout: Optional[int] = None,
        view_images: bool = False,
    ):
        super().__init__(context)
        self._system_prompt = system_prompt or _SYSTEM_PROMPT
        if view_images:
            self._system_prompt += VIEW_IMAGE_PROMPT
        self._user_prompt = user_prompt
        self._report_issues = report_issues
        self._propose_edits = propose_edits
        self._tools = tools
        self._view_images = view_images
        # Shadows the class-level `reasoning` for this instance only, so one
        # workflow can ask for more reasoning without affecting the others that
        # share this agent.
        if reasoning_effort is not None:
            self.reasoning = ReasoningDict(effort=reasoning_effort, summary="auto")
        # Same shadowing for the per-call LLM timeout: web-search turns resolve
        # every search inside one model call, so they can outlast the default.
        if timeout is not None:
            self.timeout = timeout

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> DeepAgentRun:
        # Fetched before the agent is built: the collector needs the document's
        # text to check any proposed edit against real lines, and the same file
        # tree is what the agent runs on.
        files = await self.context.file_artifacts_service.get_deepagent_backend_files(
            include_skills=True,
        )
        issue_reporter = (
            IssueReporter(
                propose_edits=self._propose_edits,
                document_text=(
                    _main_document_text(files) if self._propose_edits else None
                ),
            )
            if self._report_issues
            else None
        )
        tools = list(self._tools or ())
        if self._view_images:
            tools.append(view_image)
        if issue_reporter is not None:
            tools.extend(issue_reporter.tools)

        deep_agent = create_deep_agent(
            model=self.llm,
            tools=tools,
            context_schema=ContextSchema,
            skills=["/skills/"],
        )

        # deepagents types the compiled graph's context as None instead of
        # threading `context_schema` through; the runtime accepts it fine.
        result = await deep_agent.ainvoke(  # type: ignore[call-overload]
            {
                "files": files,
                "messages": [
                    SystemMessage(content=self._system_prompt),
                    HumanMessage(content=self._user_prompt),
                ],
            },
            config={"recursion_limit": DEEP_AGENT_RECURSION_LIMIT, **(config or {})},
            context=self.context,
        )

        # The filesystem is returned whole -- the mounted document and skills
        # alongside anything the agent wrote -- so the caller picks out what it
        # asked for by path.
        return collect_deep_agent_run(result, issue_reporter)
