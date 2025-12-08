from enum import StrEnum
from typing import Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import gpt_5_1_model
from lib.models.agent import LangChainAgent
from lib.workflows.claim_substantiation.context import ContextSchema


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
        description="Direct URL to the located source, or null if no match was found",
    )
    download_url: Optional[str] = Field(
        description="Direct URL to the downloadable version of the located source, or null if no match was found",
    )

    final_conclusion: ReferenceFetchConclusion = Field()


_system_prompt = PromptTemplate.from_template(
    """
Find the original content for a user-provided reference via web search, using the reference's details to search for the original publication online and prioritizing sources that host the full original content as referenced.

Apply a clear preference for sources that are fully publicly available and not behind a paywall. Only use paywalled sources if no publicly accessible options exist.

For each reference, follow these steps:

- Parse and extract key details: authors, title, publication/platform, date, and any identifiers (e.g., DOI).
- Reason step-by-step to identify the most reliable method for locating the source (e.g., academic search, publisher website, DOI, web search).
- Formulate an effective search query based on the extracted details.
- Locate the original webpage for the reference, preferring an official, authoritative link that provides the complete referenced work.
- Verify that the source matches the citation in terms of authorship, title, and publication date.
- Evaluate accessibility: Prefer sources that are fully accessible without a paywall. Only resort to paywalled sources if no publicly accessible copy exists.
- Check if the full content of the reference is available.
- Present findings in the required format (see below). Do not guess — if the source cannot be located, or only a paywalled version is available, explain the methods you tried and indicate the appropriate conclusion.

**Output Format (use this structure for each reference):**

- Reference details: copy as given.
- Step-by-step reasoning: describe how you searched, what sources you checked, which public and paywalled options you found, how you verified the match, and how you determined the source accessibility.
- Source URL: the direct link to the source; mark as "null" if unsuccessful.
- Download URL: the direct link to a downloadable version of the full content (for example, a PDF), or "null" if no such version is available or no source was found.
- Final conclusion: use one of
  - "Source found": the full original content is available and accessible via the Source URL and/or Download URL.
  - "Source not found": the source cannot be located.
  - "Source found but not accessible": the source exists, but the full original content is behind a paywall or otherwise inaccessible.

**Example 1 (publicly available):**

Reference: Sevilla, Jaime, Tamay Besiroglu, Ben Cottier, Josh You, Edu Roldán, Pablo Villalobos, and Ege Erdil, “Can AI Scaling Continue Through 2030?” Epoch AI, August 20, 2024.

Step-by-step reasoning: I identified the authors, title, and publication, then constructed a search query using "Can AI Scaling Continue Through 2030? Epoch AI." I reviewed results and found the official Epoch AI site, which hosts the original paper openly. I confirmed the match based on author list and publication date. There was no paywall and the full text was accessible.

Source URL: https://epochai.org/blog/can-ai-scaling-continue-through-2030

Download URL: null (full content is available directly on the page)

Final conclusion: Source found

**Example 2 (paywalled source):**

Reference: Smith, John, "Understanding Market Fluctuations," Financial Analysis Journal, March 12, 2023.

Step-by-step reasoning: I extracted the title and author, then searched the Financial Analysis Journal's website and major academic aggregators. All copies found (via journal site and JSTOR) require paid access or institutional login, and no public preprints or summaries are available. I verified these versions match in author, title, and publication date.

Source URL: https://financialanalysisjournal.example/paywalled-article

Download URL: null (download requires paid access)

Final conclusion: Source found but not accessible

**Example 3 (source not found):**

Reference: Doe, Jane, "Unpublished Insights in Data Science," Data Monthly, July 2019.

Step-by-step reasoning: I extracted the title and author, searched Data Monthly's archives, major academic sources, and web indexes. No credible results matching the citation details could be found.

Source URL: null

Download URL: null

Final conclusion: Source not found

---

**Important:**
- Always reason step-by-step before any conclusion or result; present all reasoning in the "step-by-step reasoning" section, including your approach to public accessibility/paywalls.
- Prefer non-paywalled ("publicly available") sources. If only paywalled sources are found, this must be clear in reasoning and in the final conclusion.
- Use concise, precise language, directly supporting the goal of locating the exact source.
- If complex references or edge cases arise, preserve original instruction structure and apply it.
- When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.
- Remind: Your core objective is to find and verify the original page and full content for each citation, detailing your search and verification steps, linking to the appropriate source, and quoting or explaining what is or is not accessible.
"""
)


class ReferenceFetcherAgent(LangChainAgent):
    name = "Reference Fetcher"
    description = "Fetch a reference from the internet"
    model = gpt_5_1_model
    temperature = 0.0
    output_schema = ReferenceFetchItem

    def create_llm(self):
        return init_chat_model(
            self.model.model_name,
            temperature=self.temperature,
            timeout=self.timeout,
            api_key=self.context.openai_api_key,
            reasoning={"effort": "low", "summary": "auto"},
        )

    async def ainvoke(
        self,
        input: ReferenceFetcherAgentInput,
        config: RunnableConfig = None,
    ) -> ReferenceFetchItem:
        system_prompt = _system_prompt.invoke({})

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            system_prompt=system_prompt.text,
            response_format=self.output_schema,
        )

        user_message = input.reference

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
