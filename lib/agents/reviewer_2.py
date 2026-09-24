"""Reviewer 2 agent — rigorous peer review using deep agent with file tools."""

from typing import List, Optional

from deepagents import create_deep_agent
from deepagents.backends.utils import file_data_to_string
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.tools.view_image import VIEW_IMAGE_PROMPT, view_image
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent_types import (
    DEEP_AGENT_RECURSION_LIMIT,
    report_file,
)

PEER_REVIEW_PATH = "/peer-review.md"
REBUTTAL_PATH = "/rebuttal.md"

_DELIVERY_GUIDANCE = f"""\

---

## Deliverables

Write the complete peer review to `{PEER_REVIEW_PATH}` and the complete rebuttal \
to `{REBUTTAL_PATH}` using `write_file`. These files are the only deliverables: \
the workflow reads them from the filesystem when you finish, and nothing in your \
final message is used in their place. Write each document in full, and if you \
revise one, write that file again in full.
"""


class Reviewer2Output(BaseModel):
    peer_review_markdown: str = Field(
        description="The peer review document in markdown (Sections 1-4)"
    )
    rebuttal_markdown: str = Field(description="The rebuttal document in markdown")


class Reviewer2Agent(LangChainAgent):
    name = "Reviewer 2"
    description = "Produce a rigorous peer review and rebuttal of a research document"
    model = gpt_5_6_terra_model
    temperature = 0.3
    reasoning = {"effort": "medium", "summary": "auto"}

    async def ainvoke(
        self, prompt_kwargs: dict, config: Optional[RunnableConfig] = None
    ) -> tuple[Reviewer2Output, List[BaseMessage]]:
        """Return the review and the agent's full conversation, system prompt included."""
        document_markdown = prompt_kwargs["document_markdown"]

        # A rigorous review has to see the figures it critiques; the document
        # markdown carries their `draftdetective://` srcs.
        deep_agent = create_deep_agent(
            model=self.llm,
            tools=[view_image],
            context_schema=ContextSchema,
        )

        # deepagents types the compiled graph's context as None instead of
        # threading `context_schema` through; the runtime accepts it fine.
        result = await deep_agent.ainvoke(  # type: ignore[call-overload]
            {
                "messages": [
                    SystemMessage(
                        content=load_skill_prompt("reviewer-2")
                        + _DELIVERY_GUIDANCE
                        + VIEW_IMAGE_PROMPT
                    ),
                    HumanMessage(
                        content=(
                            f"Here is the document to review:\n\n{document_markdown}"
                        )
                    ),
                ],
            },
            config={"recursion_limit": DEEP_AGENT_RECURSION_LIMIT, **(config or {})},
            context=self.context,
        )

        files = {
            path: file_data_to_string(data)
            for path, data in (result.get("files") or {}).items()
        }
        output = Reviewer2Output(
            peer_review_markdown=report_file(files, PEER_REVIEW_PATH),
            rebuttal_markdown=report_file(files, REBUTTAL_PATH),
        )
        return output, result["messages"]
