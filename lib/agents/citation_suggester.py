from enum import Enum
from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.literature_review import ReferenceType
from lib.config.llm_models import gpt_5_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class RecommendedAction(str, Enum):
    ADD_NEW_CITATION = "add_new_citation"
    CITE_EXISTING_REFERENCE_IN_NEW_PLACE = "cite_existing_reference_in_new_place"
    REPLACE_EXISTING_REFERENCE = "replace_existing_reference"
    DISCUSS_REFERENCE = "discuss_reference"
    NO_ACTION = "no_action"
    OTHER = "other"


class PublicationQuality(str, Enum):
    HIGH_IMPACT_PUBLICATION = "high_impact_publication"
    MEDIUM_IMPACT_PUBLICATION = "medium_impact_publication"
    LOW_IMPACT_PUBLICATION = "low_impact_publication"
    NOT_A_PUBLICATION = "not_a_publication"


class ConfidenceInRecommendation(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Reference(BaseModel):
    title: str = Field(
        description="Canonical title for the reference exactly as it should appear in the article's bibliography"
    )
    type: ReferenceType = Field(
        description=f"Format classification for the reference. Possible values: {[e.value for e in ReferenceType]}"
    )
    link: str = Field(
        description="Stable URL or DOI that lets the author retrieve the reference quickly"
    )
    bibliography_info: str = Field(
        description="Bibliography entry formatted in the article's style; reuse the existing entry when the source is already in the bibliography"
    )
    is_already_cited_elsewhere: bool = Field(
        description="A boolean value indicating whether the reference is already cited elsewhere in the document"
    )
    index_of_associated_existing_reference: int = Field(
        description="The index of the existing reference that this citation refers to, if any. Indices start at 1. If the citation does not refer to an existing reference in the bibliography, this should be -1."
    )
    publication_quality: PublicationQuality = Field(
        description=f"The quality of the publication that carries the suggested reference. Possible values: {[e.value for e in PublicationQuality]}"
    )
    related_excerpt: str = Field(
        description="Exact sentence or excerpt from the full document that should cite or discuss this reference"
    )
    related_excerpt_from_reference: str = Field(
        description="Exact sentence or excerpt from the reference that is why we should cite or discuss it"
    )
    rationale: str = Field(
        description="Brief explanation of why the reference strengthens, updates, or contextualizes the focused paragraph"
    )
    recommended_action: RecommendedAction = Field(
        description=(
            f"Action to take for this reference. Possible values: {[e.value for e in RecommendedAction]}"
        )
    )
    explanation_for_recommended_action: str = Field(
        description="Specific guidance for applying the recommended action, including citation placement or text revisions"
    )
    confidence_in_recommendation: ConfidenceInRecommendation = Field(
        description=f"The confidence in the recommendation. Possible values: {[e.value for e in ConfidenceInRecommendation]}"
    )


class CitationSuggestionResponse(BaseModel):
    relevant_references: list[Reference] = Field(
        description="Ordered list of the most relevant references the author should consider when revising the paragraph"
    )
    rationale: str = Field(
        description="High-level reasoning summarizing how the recommendations improve the paragraph's literature coverage"
    )


class CitationSuggestionResultWithClaimIndex(CitationSuggestionResponse):
    chunk_index: int
    claim_index: int


_citation_suggester_agent_prompt = PromptTemplate.from_template(
    """
# Role
You are an expert citation suggester tasked with ensuring a paragraph cites the strongest and most current sources available while adhering to RAND Corporation's strict attribution guidelines.

# Goal
Given the full article, its extracted bibliography, a paragraph to revise, and a literature review report, identify references that should be cited or discussed to improve that paragraph's attribution compliance. These may be:
- Existing references already listed in the bibliography but not cited in this paragraph.
- References from the literature review report that are highly relevant to the claim, chunk, and paragraph.

# RAND Attribution Requirements
You must ensure the paragraph follows RAND's Three Rules of Attribution:

1. **Ideas, Opinions, Theories, Facts, Arguments, Statistics**: If the paragraph uses any idea, opinion, theory, fact, argument, or statistic from a source, it MUST cite that source.

2. **Exact Words**: If the paragraph uses exact words from a source, it MUST cite that source and use quotation marks (or block quotes).

3. **Accurate Connection**: If a source is cited, it must be connected to the work accurately, ensuring the use remains faithful to the original author's intent.

# Instructions
1. Read the paragraph in the context of the full document and bibliography to understand the existing argument and cited sources.
2. Identify ALL instances where attribution is required but missing:
   - Unsourced facts, data, or technical details that are not common knowledge
   - Statistics, percentages, or numerical claims without citations
   - Specific claims about policies, procedures, or historical events
   - Technical descriptions or methodologies
   - Arguments or interpretations that appear to be from other sources
3. Reuse relevant bibliography entries whenever they meaningfully support the paragraph but are currently uncited. Quote the entry exactly in `bibliography_info` and include a stable link.
4. Consider references from the literature review report that are highly relevant to the claim, chunk, and paragraph and conduct focused web research for the items in the report focusing on key claims, statistics, or notable concepts that lack adequate support. Prefer authoritative sources (peer-reviewed articles, reputable institutions) and capture publication details for `bibliography_info`. Use the literature review report as a guide to the references that should be cited. Only include the reference if you think it is highly relevant to the claim, chunk, and paragraph. It is ok if you do not recommend any references from the literature review report. It is ok to double check anything you add by doing web searches, but DO NOT add references beyond those provided in the literature review report.
5. For every recommended reference:
   - Use `related_excerpt` to quote the precise sentence(s) that should cite or discuss the source.
   - Select `recommended_action` from {{"add_new_citation", "cite_existing_reference_in_new_place", "replace_existing_reference", "discuss_reference", "no_action", "other"}}.
   - In `explanation_for_recommended_action`, describe exactly where to place the citation or how to revise the text (e.g., "Add citation after the sentence describing X" or "Replace the existing citation to Y with this systematic review because …").
   - Specify what type of attribution is needed (fact, statistic, exact quote, idea, etc.)
6. Provide only high-impact recommendations (typically 1-5). Avoid duplicates and clearly distinguish whether the source comes from the existing bibliography or is newly discovered.
7. Summarize your overall reasoning in the response `rationale`, focusing on attribution compliance.
8. Do not fabricate references. If confident support cannot be found, omit the recommendation.

# Source Quality Standards
- Prefer peer-reviewed academic sources, government publications, and reputable institutions
- Avoid Wikipedia and other tertiary sources unless the research specifically focuses on user-generated content
- Verify that sources are current and authoritative
- Ensure sources are accessible to readers (provide stable URLs or DOIs when possible)
- For web sources, include access dates and stable URLs

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

## The full document that the chunk is a part of
```
{full_document}
```

## The list of bibliography entries (if any) extracted from the bibliography section of the full document
The indexes in this list should be used when returning index_of_associated_bibliography.
```
{bibliography}
```

## The paragraph of the original document that contains the chunk of text that we want to analyze
```
{paragraph}
```

## The chunk of text suggest citations for (if appropriate)
```
{chunk}
```

## The claim that is inferred from the chunk of text to be supported with additional references if appropriate
{claim}

## The list of references currently cited to support the claim and their associated supporting document (if any)
{cited_references}

## A literature review report created by the literature review agent
search for additional references. Use the literature review report as a guide to the references that should be cited. Only include the reference if you think it is highly relevant to the claim, chunk, and paragraph.
- It is NOT ok to add references beyond those provided in the literature review report.
- It is ok if you do not recommend any references from the literature review report.
- It is ok to double check anything you add by doing web searches, but do not add references beyond those provided in the literature review report.
```
{literature_review_report}
```
"""
)


class CitationSuggesterAgent(LangChainAgent):
    name = "Citation Suggester"
    description = "Review a chunk of text against RAND attribution guidelines to identify missing citations and recommend high-quality sources for proper attribution compliance"
    model = gpt_5_model
    temperature = 0.5

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> CitationSuggestionResponse:
        prompt = _citation_suggester_agent_prompt.invoke(prompt_kwargs)

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=CitationSuggestionResponse,
        )

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt.text)]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
