from enum import StrEnum
from typing import Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import gpt_5_6_terra_model, web_search_tool
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt

# Recursion limit for the agent's tool-calling loop
# Each search-download-verify cycle uses ~3 tool calls, so 50 allows ~16 cycles
REFERENCE_FETCH_RECURSION_LIMIT = 50
from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.tools.download_file_from_url import (
    download_file_from_url,
)
from lib.workflows.reference_downloader.tools.read_file_content import read_file_content


class ReferenceFetcherAgentInput(BaseModel):
    reference: str = Field(
        description="A reference to fetch, example: 'Ablon, Lillian, and Andy Bogart, Zero Days, Thousands of Nights: The Life and Times of Zero-Day Vulnerabilities and Their Exploits, RAND Corporation, RR-1751-RC, 2017. As of February 15, 2024: https://www.rand.org/pubs/research_reports/RR1751.html'"
    )


class ReferenceFetchConclusion(StrEnum):
    SOURCE_FOUND = "source_found"
    SOURCE_NOT_FOUND = "source_not_found"
    SOURCE_FOUND_BUT_NOT_ACCESSIBLE = "source_found_but_not_accessible"


class ReferenceFetchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_details: str = Field(
        description="The original reference as provided (verbatim)"
    )
    reasoning: str = Field(
        description="Step-by-step reasoning describing parsing approach, search strategies, sources checked, and how the match was verified"
    )
    source_url: Optional[str] = Field(
        description="Direct URL to the downloadable version of the located source, or null if no match was found",
    )
    file_id: Optional[str] = Field(
        description="The ID of the verified downloaded file containing the full original content. Return null if conclusion is different than 'source_found'",
    )
    final_conclusion: ReferenceFetchConclusion = Field()
    inaccessibility_reason: Optional[str] = Field(
        default=None,
        description="A single sentence explaining why the content is not accessible. Only set when final_conclusion is 'source_found_but_not_accessible'.",
    )


# Backend-specific addendum appended to the portable `reference-download` skill.
# The skill itself is tool-agnostic; this maps it onto Draft Detective's concrete
# tools and the structured `ReferenceFetchItem` output fields.
_ENV_GUIDANCE = """\

---

## Tools and output in this environment

You have these tools:
- a web search tool to find candidate URLs;
- `download_file_from_url`: downloads a file from a URL and returns a **file ID** for the saved file;
- `read_file_content`: returns the content of a downloaded file given its file ID, so you can verify it.

Map the outcome to your structured result:
- Set `final_conclusion` to `source_found` (the skill's "found"), `source_found_but_not_accessible` ("found but not accessible"), or `source_not_found` ("not found").
- On `source_found`, set `file_id` to the confirmed downloaded file's ID and `source_url` to the URL it came from. For any other conclusion, leave `file_id` null.
- On `source_found_but_not_accessible`, set `inaccessibility_reason` to the one-sentence explanation.
"""


class ReferenceFetcherAgent(LangChainAgent):
    name = "Reference Fetcher"
    description = "Fetch a reference from the internet"
    model = gpt_5_6_terra_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(  # type: ignore[override]
        self,
        input: ReferenceFetcherAgentInput,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[ReferenceFetchItem, list[BaseMessage]]:
        system_prompt = load_skill_prompt("reference-download") + _ENV_GUIDANCE
        agent = create_agent(
            self.llm,
            [web_search_tool(self.model), download_file_from_url, read_file_content],
            system_prompt=system_prompt,
            context_schema=ContextSchema,
            response_format=ReferenceFetchItem,
        ).with_retry(stop_after_attempt=2)

        user_message = input.reference

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={
                **(config or {}),
                "recursion_limit": REFERENCE_FETCH_RECURSION_LIMIT,
            },
            context=self.context,
        )

        # `system_prompt` is sent with every model call but is not part of the
        # agent's message history; prepend it so the saved conversation shows
        # everything the model was given.
        messages = [SystemMessage(content=system_prompt), *result["messages"]]
        return result["structured_response"], messages
