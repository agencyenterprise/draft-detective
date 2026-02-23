import logging
from enum import Enum
from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)


class LitRecommendedAction(str, Enum):
    ADD_NEW_CITATION = "add_new_citation"
    CITE_EXISTING_REFERENCE_IN_NEW_PLACE = "cite_existing_reference_in_new_place"
    REPLACE_EXISTING_REFERENCE = "replace_existing_reference"
    DISCUSS_REFERENCE = "discuss_reference"
    NO_ACTION = "no_action"
    OTHER = "other"


class ReferenceType(str, Enum):
    # Academic publications that have undergone formal peer review
    PEER_REVIEWED_PUBLICATION = "peer_reviewed_publication"

    # Preliminary research that hasn't completed peer review
    PREPRINT = "preprint"

    # Published books and book chapters
    BOOK = "book"

    # Official reports from government agencies and NGOs that are not peer reviewed
    GOVERNMENT_NGO_REPORT = "government_ngo_report"

    # Research data, code and software artifacts
    DATA_SOFTWARE = "data_software"

    # Journalism and media publications
    NEWS_MEDIA = "news_media"

    # Reference works and encyclopedic content
    REFERENCE = "reference"

    # Online and web-based content like blogs, wikis, social media, etc.
    WEBPAGE = "webpage"


# applies to the evidence
class ReferenceDirection(str, Enum):
    SUPPORTING = "supporting"
    CONFLICTING = "conflicting"
    MIXED = "mixed"
    CONTEXTUAL_ONLY = "contextual"


class PoliticalBias(str, Enum):
    CONSERVATIVE = "conservative"
    LIBERAL = "liberal"
    OTHER = "other"


class QualityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentReferenceFactors(BaseModel):
    """A reference that should be cited or discussed in the article"""

    title: str = Field(description="The title of the reference")
    authors: str = Field(description="Authors of the source")
    publication_year: int = Field(description="Year of publication")
    bibliography_info: str = Field(description="Full bibliography citation text")
    link: str | None = Field(
        default=None, description="URL or DOI link to the reference"
    )
    reference_excerpt: str = Field(
        description="Relevant excerpt from the reference that is why we should cite or discuss it"
    )
    reference_type: ReferenceType = Field(
        description="Publication type (e.g., journal, website, book, preprint)"
    )
    quality: QualityLevel = Field(description="Quality of the reference")
    reference_direction: ReferenceDirection = Field(
        description="Type of source: supporting, conflicting, or contextual"
    )
    political_bias: PoliticalBias = Field(description="Political bias of the evidence")
    rationale: str = Field(description="Why this reference should be cited")
    main_document_excerpt: str = Field(
        description="Relevant excerpt from the main document that relates to this reference"
    )
    recommended_action: str = Field(
        description=f"What action to take ({', '.join([e.value for e in LitRecommendedAction])}"
    )
    explanation_for_recommended_action: str = Field(
        description="How to implement the recommended action"
    )


# note (2025-10-14): for the deep research model, the pydantic data models are not used and the format of the
# frontend is not setup to use the existing structure of the models. So we might modify this format.
class LiteratureReviewResponse(BaseModel):
    relevant_references: list[DocumentReferenceFactors] = Field(
        default_factory=list, description="List of relevant references to cite"
    )
    rationale: str = Field(
        description="Overall rationale for the literature review recommendations"
    )


_literature_review_agent_prompt = PromptTemplate.from_template(
    """
# Role
You are an expert literature review researcher tasked with ensuring an article cites the highest quality and most current sources available. However, if the document publication date is provided, you are only to look for references that come BEFORE the document publication date.

# Goal
Given the full article and its extracted bibliography, identify references that should be cited or discussed to improve the article. These may be:
- Existing references already listed in the bibliography but not cited in some of the places they should be cited in.
- New, high-quality references found via web research.

# Instructions
1. Read the full document and bibliography carefully to understand the existing arguments and cited sources for each.
2. Create a comprehensive report with the following components:
- Information about topics of discussion
- Relevant high quality references about each topic and how they could fit in the document as citations.

# Output Format
For each relevant reference, provide:
- **title**: The title of the reference
- **authors**: Authors of the source
- **publication_year**: Year of publication
- **bibliography_info**: Full bibliography citation text
- **link**: URL or DOI link to the reference (if available)
- **reference_excerpt**: Relevant excerpt from the reference that is why we should cite or discuss it
- **reference_type**: Publication type (peer_reviewed_publication, government_ngo_report, news_media, book, preprint, data_software, reference, webpage)
- **quality**: Quality of the reference (high, medium, low)
- **reference_direction**: Type of source (supporting, conflicting, mixed, contextual)
- **political_bias**: Political bias of the evidence (conservative, liberal, other)
- **rationale**: Why this reference should be cited
- **main_document_excerpt**: Relevant excerpt from the main document that relates to this reference
- **recommended_action**: What action to take (add_new_citation, cite_existing_reference_in_new_place, replace_existing_reference, discuss_reference, no_action, other)
- **explanation_for_recommended_action**: How to implement the recommended action

Also provide an overall **rationale** summarizing your literature review recommendations.

Remember:
- If the document publication date is provided, you are only to look for references that come BEFORE the document publication date.
- Do not fabricate any references. If relevance to the claims cannot be found, omit the recommendation.

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

## Document publication date
{document_publication_date}

## Full article
```
{full_document}
```

## Extracted bibliography
```
{bibliography}
```
"""
)


class LiteratureReviewAgent(LangChainAgent):
    name = "Literature Review Researcher"
    description = "Review a document paragraph against the article bibliography and recent literature to propose citation updates"
    model = gpt_5_2_model
    temperature = 0.5
    timeout = 600
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> LiteratureReviewResponse:
        prompt = _literature_review_agent_prompt.invoke(prompt_kwargs)

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=LiteratureReviewResponse,
        )

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt.text)]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
