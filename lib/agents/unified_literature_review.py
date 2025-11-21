import logging
from enum import Enum
from typing import Literal, Optional, Union

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.langfuse import langfuse_handler
from lib.config.llm_models import LLMModel, gpt_5_model, gpt_5_mini_model
from lib.models.agent import DirectOpenAIAgent
from lib.services.openai import (
    ensure_structured_output_response,
    wait_for_response,
)

logger = logging.getLogger(__name__)


# Shared Enums
class ReferenceType(str, Enum):
    """Publication type enum"""

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


class ReferenceDirection(str, Enum):
    """Evidence direction enum - applies to the evidence"""

    SUPPORTING = "supporting"
    CONFLICTING = "conflicting"
    MIXED = "mixed"
    CONTEXTUAL_ONLY = "contextual"


class PoliticalBias(str, Enum):
    """Political bias classification"""

    CONSERVATIVE = "conservative"
    LIBERAL = "liberal"
    OTHER = "other"


class QualityLevel(str, Enum):
    """Source quality level"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LitRecommendedAction(str, Enum):
    """Recommended action for literature review references"""

    ADD_NEW_CITATION = "add_new_citation"
    CITE_EXISTING_REFERENCE_IN_NEW_PLACE = "cite_existing_reference_in_new_place"
    REPLACE_EXISTING_REFERENCE = "replace_existing_reference"
    DISCUSS_REFERENCE = "discuss_reference"
    NO_ACTION = "no_action"
    OTHER = "other"


# Unified Models
class ReferenceFactors(BaseModel):
    """Unified reference factors model combining DocumentReferenceFactors and ClaimReferenceFactors"""

    title: str = Field(description="Title of the source")
    authors: str = Field(description="Authors of the source")
    publication_year: int = Field(description="Year of publication")
    bibliography_info: str = Field(
        description="Bibliography entry formatted in the article's style"
    )
    link: Optional[str] = Field(
        default=None, description="URL or DOI link to the source"
    )
    reference_excerpt: str = Field(
        description="Relevant excerpt from the source that is why we should cite or discuss it"
    )
    reference_type: ReferenceType = Field(description="Publication type of the source")
    reference_direction: ReferenceDirection = Field(
        description="Type of source: supporting, conflicting, or contextual"
    )
    quality: QualityLevel = Field(
        description="Source quality level: high, medium, or low"
    )
    political_bias: PoliticalBias = Field(description="Political bias of the evidence")
    rationale: str = Field(
        description="Why this source is relevant and why it has this quality level"
    )
    methodology: Optional[str] = Field(
        default=None, description="Notes about study methodology or data quality"
    )
    main_document_excerpt: Optional[str] = Field(
        default=None,
        description="Relevant excerpt from the main document that relates to this reference",
    )
    recommended_action: Optional[str] = Field(
        default=None,
        description=f"What action to take ({', '.join([e.value for e in LitRecommendedAction])})",
    )
    explanation_for_recommended_action: Optional[str] = Field(
        default=None, description="How to implement the recommended action"
    )


# Response Models
class UnifiedLiteratureReviewResponse(BaseModel):
    """Response model for document-level literature reviews"""

    relevant_references: list[ReferenceFactors] = Field(
        default_factory=list, description="List of relevant references to cite"
    )
    rationale: str = Field(
        description="Overall rationale for the literature review recommendations"
    )


class UnifiedLiveLiteratureReviewResponse(BaseModel):
    """Response model for claim-level literature reviews"""

    claim: str = Field(description="The claim that was reviewed")
    newer_references: list[ReferenceFactors] = Field(
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


# Prompt Template Builder
def _get_time_filter_config(
    time_filter: Literal["before", "after"], prompt_kwargs: dict
) -> dict:
    """Get role, goal, and time instruction based on time filter"""
    pub_date = prompt_kwargs.get("document_publication_date", "N/A")

    configs = {
        "after": {
            "role": """# Role
You are an expert literature review researcher specializing in finding newer evidence that could update or contextualize existing claims in research documents. You look for all available literature that is relevant to the claim. However, if the document publication date is provided, you are only to look for references that come AFTER the document publication date.""",
            "goal": """# Goal
Given a claim from a document and the document's publication date, find newer literature (published AFTER the document's publication date) that provides supporting, conflicting, or contextual evidence for the claim. As additional context, you will also be given the argument summary of the document, the paragraph containing the claim, the specific chunk containing the claim, and the original claim being analyzed.""",
            "time_instruction": f"ONLY search for literature published AFTER the document's publication date ({pub_date}); Do not present sources that are older than the document's publication date.",
            "time_direction": "AFTER the document's publication date",
        },
        "before": {
            "role": """# Role
You are an expert literature review researcher tasked with ensuring an article cites the highest quality and most current sources available. However, if the document publication date is provided, you are only to look for references that come BEFORE the document publication date.""",
            "goal": """# Goal
Given the full article and its extracted bibliography, identify references that should be cited or discussed to improve the article. These may be:
- Existing references already listed in the bibliography but not cited in some of the places they should be cited in.
- New, high-quality references found via web research.""",
            "time_instruction": f"If the document publication date is provided, you are only to look for references that come BEFORE the document publication date ({pub_date}).",
            "time_direction": "BEFORE the document's publication date",
        },
    }
    return configs[time_filter]


def _get_claim_instructions_template() -> str:
    """Get instructions template for claim-level scope"""
    return """# Instructions
1. **Search Strategy**: Use web search to find recent literature published {time_direction}
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
- {time_instruction}
- Use specific search terms related to the claim's key concepts
- If a reference is already cited in the document, then do not include it in the newer references
- Include variations of terminology and synonyms
- Search for both references that support the claim and references that contradict the claim
- Look for meta-analyses, systematic reviews, and large-scale studies when available
- Consider different disciplinary perspectives if relevant"""


def _get_document_instructions_template() -> str:
    """Get instructions template for document-level scope"""
    return """# Instructions
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
- {time_instruction}
- Do not fabricate any references. If relevance to the claims cannot be found, omit the recommendation."""


def _get_claim_context(prompt_kwargs: dict) -> str:
    """Get context section for claim-level scope"""
    return """## Document Context
**Domain**: {domain_context}
**Target Audience**: {audience_context}
**Document Publication Date**: {document_publication_date}

## The argument summary of the document
```
{document_summary}
```

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
```""".format(
        domain_context=prompt_kwargs.get("domain_context", ""),
        audience_context=prompt_kwargs.get("audience_context", ""),
        document_publication_date=prompt_kwargs.get("document_publication_date", ""),
        document_summary=prompt_kwargs.get("document_summary", ""),
        paragraph=prompt_kwargs.get("paragraph", ""),
        claim=prompt_kwargs.get("claim", ""),
        bibliography=prompt_kwargs.get("bibliography", ""),
    )


def _get_document_context(prompt_kwargs: dict) -> str:
    """Get context section for document-level scope"""
    return """## Document publication date
{document_publication_date}

## Full article
```
{full_document}
```

## Extracted bibliography
```
{bibliography}
```""".format(
        document_publication_date=prompt_kwargs.get("document_publication_date", ""),
        full_document=prompt_kwargs.get("full_document", ""),
        bibliography=prompt_kwargs.get("bibliography", ""),
    )


def _build_unified_prompt(
    time_filter: Literal["before", "after"],
    scope: Literal["document", "claim"],
    prompt_kwargs: dict,
) -> str:
    """Build unified prompt based on time_filter and scope parameters"""

    # Get time filter configuration
    time_config = _get_time_filter_config(time_filter, prompt_kwargs)

    # Get instructions based on scope
    if scope == "claim":
        instructions_template = _get_claim_instructions_template()
        instructions_section = instructions_template.format(
            time_direction=time_config["time_direction"],
            time_instruction=time_config["time_instruction"],
        )
        context_section = _get_claim_context(prompt_kwargs)
    else:  # document
        instructions_template = _get_document_instructions_template()
        instructions_section = instructions_template.format(
            time_instruction=time_config["time_instruction"],
        )
        context_section = _get_document_context(prompt_kwargs)

    # Combine all sections
    return f"""{time_config["role"]}

{time_config["goal"]}

{instructions_section}

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

{context_section}"""


# Unified Agent Class
class UnifiedLiteratureReviewAgent(DirectOpenAIAgent):
    """Unified agent for both document-level and claim-level literature reviews"""

    name = "Unified Literature Review Researcher"
    description = "Review documents and claims against bibliography and literature to propose citation updates"
    temperature = 0.5

    def __init__(self, default_model=None):
        """Initialize with optional default model override"""
        super().__init__()
        self._default_model = default_model

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        time_filter: Literal["before", "after"] = "before",
        scope: Literal["document", "claim"] = "document",
        model_override: Optional[LLMModel] = None,
        config: RunnableConfig = None,
    ) -> Union[UnifiedLiteratureReviewResponse, UnifiedLiveLiteratureReviewResponse]:
        """
        Invoke the unified literature review agent

        Args:
            prompt_kwargs: Dictionary of prompt variables
            time_filter: Filter for publication date ("before" or "after")
            scope: Scope of review ("document" or "claim")
            model_override: Optional LLMModel override
            config: Optional RunnableConfig

        Returns:
            UnifiedLiteratureReviewResponse for document scope
            UnifiedLiveLiteratureReviewResponse for claim scope
        """
        # Determine model to use
        if model_override:
            model = model_override
        elif self._default_model:
            model = self._default_model
        elif scope == "claim":
            model = gpt_5_mini_model
        else:  # document
            model = gpt_5_model

        # Build prompt
        prompt_text = _build_unified_prompt(time_filter, scope, prompt_kwargs)
        input = [{"role": "user", "content": prompt_text}]

        # Determine response format
        if scope == "claim":
            response_format = UnifiedLiveLiteratureReviewResponse
        else:
            response_format = UnifiedLiteratureReviewResponse

        # Determine if background processing is needed (document-level uses background)
        use_background = scope == "document"

        # Make API call
        response = await self.client.responses.parse(
            model=model.name,
            tools=[{"type": "web_search"}],
            max_tool_calls=20,
            reasoning=(
                {"effort": "low", "summary": "auto"} if scope == "document" else None
            ),
            text_format=response_format,
            background=use_background,
            input=input,
        )

        # Wait for response if background processing was used
        if use_background:
            response = await wait_for_response(
                self.client, response, log_info="Unified Literature Review Researcher"
            )

        return ensure_structured_output_response(response, response_format)


# Agent instance
unified_literature_review_agent = UnifiedLiteratureReviewAgent()

# Aliases for backward compatibility
ClaimReferenceFactors = ReferenceFactors
DocumentReferenceFactors = ReferenceFactors
