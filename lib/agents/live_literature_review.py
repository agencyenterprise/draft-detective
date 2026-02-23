from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.literature_review import (
    PoliticalBias,
    QualityLevel,
    ReferenceDirection,
    ReferenceType,
)
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class ClaimReferenceFactors(BaseModel):
    """A newer source that provides evidence for or against a claim"""

    title: str = Field(description="Title of the source")
    authors: str = Field(description="Authors of the source")
    publication_year: int = Field(description="Year of publication")
    bibliography_info: str = Field(
        description="Bibliography entry formatted in the article's style"
    )
    link: str = Field(description="URL or DOI link to the source")
    reference_excerpt: str = Field(description="Relevant excerpt from the source")
    reference_type: ReferenceType = Field(description="Publication type of the source")
    reference_direction: ReferenceDirection = Field(
        description="Type of source: supporting, conflicting, or contextual"
    )
    quality: QualityLevel = Field(
        description="Source quality level: high, medium, or low"
    )
    political_bias: PoliticalBias = Field(description="Political bias of the evidence")
    rationale: str = Field(
        description="Why this source is relevant to the claim and the claim's evidence alignment and why does it have this quality level. In a maximum of THREE sentences."
    )
    methodology: str = Field(
        description="Notes about study methodology or data quality"
    )


class LiveLiteratureReviewResponse(BaseModel):
    claim: str = Field(description="The claim that was reviewed")
    newer_references: list[ClaimReferenceFactors] = Field(
        default_factory=list,
        description="List of newer sources found after the document publication date",
    )
    references_summary: str = Field(
        description="Summary of the overall references landscape for this claim"
    )
    publication_date_filter: str = Field(
        description="The publication date (YYYY-MM-DD) used as the filter cutoff"
    )
    search_strategy: str = Field(
        description="Description of the search strategy used to find sources"
    )


_live_literature_review_agent_prompt = PromptTemplate.from_template(
    """
# Role
You are an expert literature review researcher specializing in finding newer evidence that could update or contextualize existing claims in academic and policy documents.

# Goal
Given a claim from a document and the document's publication date, find newer literature (published after the document's publication date) that provides supporting, conflicting, or contextual evidence for the claim. As additional context, you will also be given the argument summary of the document, the paragraph containing the claim, the specific chunk containing the claim, and the original claim being analyzed.

# Instructions
1. **Search Strategy**: Use web search to find recent literature published AFTER the document's publication date ({document_publication_date})
2. **Reference Direction**: For each source found, classify the reference as:
   - **Supporting**: Directly supports or strengthens the claim
   - **Conflicting**: Contradicts or challenges the claim
   - **Mixed**: Provides mixed evidence for the claim
   - **Contextual Only**: Provides additional context without directly supporting or conflicting

## Reference Classification Guidelines

For each piece of evidence
- reference direction
- quality
- publication type
- political bias

### Direction of Reference Assessment
Provide each piece of evidence related to a claim with one of the following direction labels:
- **Supporting**: Considering the collection of highest quality new and old sources reveals that the most authoritative and highest quality sources support the claim. Thus the claim needs to be updated with sources
- **Conflicting**: Considering the collection of highest quality new and old sources reveals that the most authoritative and highest quality sources CONFLICT with the claim. Thus the claim needs to be updated with sources and to define the counter statement.
- **Mixed**: Considering the collection of highest quality new and old sources reveals that the most authoritative and highest quality sources provide a MIXED resolution to the claim. Thus the claim needs to be updated with sources and to reflect this mixed perspective.
- **Contextual Only**: Sources provide context but don't directly support or conflict with the claim.

### Political Leaning of Reference Assessment
Provide each piece of evidence related to a claim with one of the following political leaning labels:
- **Conservative**: Sources that support conservative values, policies, or viewpoints
- **Liberal**: Sources that support liberal values, policies, or viewpoints
- **Other**: Sources that are neither conservative nor liberal in bias

### Publication Type of Reference Assessment
- peer_reviewed_publication: Articles found in high quality academic journals
- preprint: Articles found in preprint servers, unpublished theses, working papers
- book: monographs, edited volumes, chapters, textbooks
- government_ngo_report: white papers, policy briefs, reports from government agencies, non-government organizations
- data_software: data sets, software, code, databases
- news_media: newspapers, magazines
- reference: encyclopedia, dictionary, almanac, atlas, yearbook, bibliographies, bibliographies, etc.
- webpage: websites, blogs, wikis, social media, etc.

### Quality of Evidence Assessment
Provide each piece of evidence related to a claim with one of the following quality labels:
- **High**: Peer-reviewed academic sources, government agencies, established institutions, with high quality methodology and little to no potential bias
- **Medium**: Reputable news sources, think tanks with clear methodology, professional organizations, with moderate methodology and potential bias
- **Low**: Blogs, opinion pieces, sources with unclear methodology or potential bias

# Output Requirements
- Return at most THREE high-quality references per claim. Only return a full set of THREE if all three are high quality and relevant to the claim.
- Prioritize peer-reviewed academic sources, government reports, and reputable institutions
- Focus on more recent high quality references from the last 5 years
- Provide specific excerpts that demonstrate the reference relationship
- Explain the methodology and quality factors for each source
- Focus on the highest quality and most relevant sources only
- In the rationale, explain why the source is relevant to the claim and why it has this quality level, in a maximum of THREE sentences.

# Search Guidelines
- ONLY search for literature published AFTER the document's publication date ({document_publication_date}); Do not present sources that are older than the document's publication date.
- Use specific search terms related to the claim's key concepts
- When presenting links to the references, use the full URL of the reference and not just a link to the site's main page
- If a reference is already cited in the document, then do not include it in the newer references
- Include variations of terminology and synonyms
- Search for both references that support the claim and references that contradict the claim
- Look for meta-analyses, systematic reviews, and large-scale studies when available
- Consider different disciplinary perspectives if relevant

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

# Agent Inputs

{domain_context}

{audience_context}

**Document Publication Date**: {document_publication_date}

{summary_context}

## The paragraph containing the claim
```
{paragraph}
```

## The specific claim to analyze for newer evidence
```
{claim}
```

## Current bibliography from the document (for reference)
```
{bibliography}
```
"""
)


class LiveLiteratureReviewAgent(LangChainAgent):
    name = "Live Literature Review Researcher"
    description = (
        "Find newer literature that could update or contextualize existing claims"
    )
    model = gpt_5_mini_model
    temperature = 0.5

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> LiveLiteratureReviewResponse:
        prompt = _live_literature_review_agent_prompt.invoke(prompt_kwargs)

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=LiveLiteratureReviewResponse,
        )

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt.text)]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
