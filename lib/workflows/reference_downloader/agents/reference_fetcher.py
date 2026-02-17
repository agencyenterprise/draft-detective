from enum import StrEnum
from typing import Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent

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


_system_prompt = PromptTemplate.from_template(
    """
Locate the full original content of a user-provided reference with web search; download and verify its completeness; report failure if needed.

- When given a reference (e.g., citation or bibliographic entry), use web search tool to locate a direct URL for the full, original content of the reference (not an abstract, summary, or metadata-only page).
- Upon finding a candidate full-content URL, use the available tool to download the file; this tool will return a file ID for the downloaded file.
- Next, validate the downloaded file: use the provided tool to read/check the file by its ID, ensuring it matches the full original content described in the reference (e.g., contains correct title, authors, and full text/content).
- If the file is confirmed as the correct full original content, return the downloaded file ID and stop.
- If the download does not contain the full content (e.g., is incomplete, paywalled, preview-only, or mismatched), resume searching for a different URL hosting the full content; repeat the process.
- Continue searching and verifying until either the correct file is found or all viable options are exhausted.
- As "final_conclusion", return one of the following:
  - "source_found": the full original content is available and accessible; you read the file and confirmed it matches the reference.
  - "source_found_but_not_accessible": the source exists, but the full original content is behind a paywall or otherwise inaccessible; you download the file but it does not match the reference. You MUST also set "inaccessibility_reason" to a single concise sentence explaining why the content is not accessible (e.g., "The content is behind a JSTOR paywall requiring institutional login.", "The site uses Cloudflare bot protection that blocks automated downloads.", "Access requires a paid subscription to the publisher's platform.").
  - "source_not_found": the source cannot be located; the online presence of the source cannot be confirmed.

Follow this sequence strictly:
REASONING (search, download, verify, repeat as needed) → CONCLUSION

## Example

**Input:**
Ablon, Lillian, and Andy Bogart, Zero Days, Thousands of Nights: The Life and Times of Zero-Day Vulnerabilities and Their Exploits, RAND Corporation, RR-1751-RC, 2017. As of February 15, 2024: https://www.rand.org/pubs/research_reports/RR1751.html

**Process (REASONING FIRST):**
- Search online using the full citation to find the official or reputable link (RAND's official report page) hosting the report.
- Confirm the link points to the full PDF (not a summary).
- Download the linked PDF.
- Read the downloaded file, check metadata: title, author, and full text match reference.
- If all criteria met, accept and return file ID.
- If not, try 2-3 alternative sources. If all fail with paywall/access issues, conclude "source_found_but_not_accessible".
- If all efforts fail to locate the source, return "source_not_found".

(Reminder: Always start your output with your reasoning and ensure that you do not output any conclusions before finishing your verification steps. This order is required.)

---

**Important:**
- Always perform reasoning steps (search, download, validate) before answering.
"""
)


class ReferenceFetcherAgent(LangChainAgent):
    name = "Reference Fetcher"
    description = "Fetch a reference from the internet"
    model = gpt_5_2_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        input: ReferenceFetcherAgentInput,
        config: Optional[RunnableConfig] = None,
    ) -> ReferenceFetchItem:
        system_prompt = _system_prompt.invoke({})

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}, download_file_from_url, read_file_content],
            system_prompt=system_prompt.text,
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

        return result["structured_response"]
