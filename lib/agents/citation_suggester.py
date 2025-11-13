import asyncio
from enum import Enum

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.literature_review import ReferenceType
from lib.config.llm_models import gpt_5_model
from lib.models.agent import AgentProtocol
from lib.services.openai import ensure_structured_output_response, get_openai_client


class RecommendedAction(str, Enum):
    ADD_NEW_CITATION = "add_new_citation"
    CITE_EXISTING_REFERENCE_IN_NEW_PLACE = "cite_existing_reference_in_new_place"
    REPLACE_EXISTING_REFERENCE = "replace_existing_reference"
    DISCUSS_REFERENCE = "discuss_reference"
    NO_ACTION = "no_action"
    OTHER = "other"


class PublicationQuality(str, Enum):  # TODO: play with these options
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
        description="Format classification for the reference (webpage, book, article, or other)"
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
        description="The quality of the publication that carries the suggested reference"
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
            "Action to take for this reference: add_citation, replace_existing_reference, discuss_reference, no_action, or other"
        )
    )
    explanation_for_recommended_action: str = Field(
        description="Specific guidance for applying the recommended action, including citation placement or text revisions"
    )
    confidence_in_recommendation: ConfidenceInRecommendation = Field(
        description="The confidence in the recommendation"
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
   - Select `recommended_action` from {{"add_citation", "replace_existing_reference", "discuss_reference", "no_action", "other"}}.
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


class CitationSuggesterAgent(AgentProtocol):
    name: str = "Citation Suggester"
    description: str = (
        "Review a chunk of text against RAND attribution guidelines to identify missing citations and recommend high-quality sources for proper attribution compliance"
    )

    def __init__(self):
        self.client = get_openai_client()

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> CitationSuggestionResponse:
        prompt = _citation_suggester_agent_prompt.invoke(prompt_kwargs)
        input = [{"role": "user", "content": prompt.text}]

        response = await self.client.responses.parse(
            model=gpt_5_model.name,
            tools=[{"type": "web_search"}],
            max_tool_calls=20,
            # reasoning={
            #     "effort": "low",  # "minimal", "low", "medium", "high"
            #     "summary": "auto",
            # },
            text_format=CitationSuggestionResponse,
            input=input,
        )

        return ensure_structured_output_response(response, CitationSuggestionResponse)


citation_suggester_agent = CitationSuggesterAgent()

if __name__ == "__main__":
    response = asyncio.run(
        citation_suggester_agent.ainvoke(
            {
                "full_document": """# Some statistics about the office of the US president
Over the course of the US history, the office of the US president has changed hand dozens of times. Various types of exchanges has happened, ranging from the same president being elected more than twice (i.e., Franklin D. Roosevelt) to the president being removed from office (i.e., Andrew Johnson).

One thing that has never happened, is that a one-term president comes back to office in a later term after losing one reelection bid. So surely, based on this track record alone it seems exceedingly unlikely that former president Trump would be able to defeat President Joe Biden in the 2024 election.
""",
                "bibliography": """Foner, E. (2014). Reconstruction: America's Unfinished Revolution, 1863-1877. New York, NY: Harper & Row.
Skowronek, S. (2011). Presidential Leadership in Political Time. Lawrence, KS: University Press of Kansas.
""",
                "paragraph": """One thing that has never happened, is that a one-term president comes back to office in a later term after losing one reelection bid. So surely, based on this track record alone it seems exceedingly unlikely that former president Trump would be able to defeat President Joe Biden in the 2024 election.""",
                "chunk": """One thing that has never happened, is that a one-term president comes back to office in a later term after losing one reelection bid. So surely, based on this track record alone it seems exceedingly unlikely that former president Trump would be able to defeat President Joe Biden in the 2024 election.""",
                "claim": """So surely, based on this track record alone it seems exceedingly unlikely that former president Trump would be able to defeat President Joe Biden in the 2024 election.""",
                "cited_references": """""",
                "literature_review_report": """Below is a structured, topic-by-topic briefing you can use to improve the article. For each topic, I list what’s currently in the text, what’s inaccurate or under-supported, and high-quality sources you can cite. I also indicate how these sources could be integrated into the article.

Executive snapshot
- Main issues to fix or qualify:
  - A number of factual inaccuracies about impeachment and removal (Andrew Johnson was impeached but not removed).
  - A concrete counterexample to the claim that “a one-term president never returns after losing reelection” (Grover Cleveland served two nonconsecutive terms).
  - The article’s projection about the 2024 election should be grounded in actual results and credible analysis.
  - The article could benefit from situating its claims within established political-time/theory literatures (Skowronek) and reconstructive history (Foner) to avoid overly simplistic historical generalizations.
- Strong, current sources exist to correct or nuance these points (see topic-by-topic below).

Topic 1. The claim that Andrew Johnson was “removed from office” (impeachment vs removal)
What’s in the article
- “the president being removed from office (i.e., Andrew Johnson)” implies Johnson was removed from office through impeachment.

What’s wrong or under-supported
- Andrew Johnson was impeached by the House but was acquitted by the Senate and thus not removed from office. This is a classic historical point that is routinely misunderstood.

Recommended high-quality sources to cite
- Britannica: Andrew Johnson – The presidency (impeachment section; explicit note that Johnson was impeached but not removed). ([britannica.com](https://www.britannica.com/biography/Andrew-Johnson?utm_source=openai))
- U.S. Senate: Impeachment Trial of Andrew Johnson (official pages detailing the trial and the acquittal by the Senate). ([senate.gov](https://www.senate.gov/about/powers-procedures/impeachment/impeachment-johnsonandrew.htm?utm_source=openai))
- National Archives: Impeachment (historical overview and the Johnson impeachment’s fate). ([archives.gov](https://www.archives.gov/legislative/features/impeachment?utm_source=openai))
- History.com (for accessible summary of the Johnson impeachment and a comparison to later impeachments). ([history.com](https://www.history.com/this-day-in-history/president-andrew-johnson-impeached?utm_source=openai))

How to fit this in the document
- Replace or revise the phrasing “the president being removed from office (i.e., Andrew Johnson)” with a sentence that clarifies:
  - Johnson was impeached by the House in 1868 but was not removed after the Senate trial (acquitted by one vote). Then briefly note that impeachment is a political process, not automatic removal. Use the Britannica and Senate/NARA sources to anchor this correction. ([britannica.com](https://www.britannica.com/biography/Andrew-Johnson?utm_source=openai))

Topic 2. Grover Cleveland as a counterexample to “one-term presidents never return”
What’s in the article
- The piece implies a one-term president has never returned to win office in a later term after losing reelection.

What’s wrong or under-supported
- Grover Cleveland is the famous counterexample: he served as the 22nd president (1885–1889), lost the 1888 election, and then won again as the 24th president (1893–1897), making him the only president to serve two nonconsecutive terms.

Recommended high-quality sources to cite
- Britannica: Grover Cleveland – biography and the fact he served nonconsecutive terms (22nd and 24th). ([britannica.com](https://www.britannica.com/biography/Grover-Cleveland?utm_source=openai))
- Britannica: Grover Cleveland (overview) – reinforcing the “nonconsecutive terms” point. ([britannica.com](https://www.britannica.com/biography/Grover-Cleveland?utm_source=openai))
- History.com or NPR summaries (for accessible narrative of his two terms). See History.com’s Grover Cleveland article. ([history.com](https://www.history.com/articles/grover-cleveland?utm_source=openai))
- AP coverage (for contemporary framing that Trump’s situation in 2024 has publicized Cleveland’s precedent). ([apnews.com](https://apnews.com/article/7ea2c92c72911462ccb1bc2e7352fa23?utm_source=openai))

How to fit this in the document
- After the sentence about the “never comes back” claim, insert a brief corrective note: “Grover Cleveland is the sole counterexample of a president who served two nonconsecutive terms; he was the 22nd and 24th president (1885–1889 and 1893–1897).” Cite Britannica (turn0search0 or turn3search2) for the factual claim, and optionally include a secondary note with History.com or NPR for public-facing context (turn3search5). ([britannica.com](https://www.britannica.com/biography/Grover-Cleveland?utm_source=openai))


Topic 3. Theoretical framing: Skowronek’s presidential leadership in political time
What’s in the bibliography now
- Skowronek (2011). Presidential Leadership in Political Time.

What’s missing or could be strengthened
- The article would benefit from clearly signaling how these works illuminate patterns of presidential power, legitimacy, and transitions—especially when discussing nonconsecutive terms, impeachments, or dramatic political realignments.

Recommended high-quality sources to cite (to connect theory to the article)
- Skowronek, Presidential Leadership in Political Time (2008 edition; reprise and reappraisal). The Yale department page and Cambridge/academic reviews provide accessible summaries and critical receptions.

How to fit this in the document
- Add a short “theoretical framing” paragraph or footnotes:
  - Provide a caution that Skowronek’s theory emphasizes historical patterns but does not predict individual outcomes with certainty; cite the Cambridge review for a critical perspective. ([politicalscience.yale.edu](https://politicalscience.yale.edu/publications/presidential-leadership-political-time-reprise-and-reappraisal-third-edition?utm_source=openai))


Topic 4. Reconstruction and the current argument’s broader narrative
What’s in the bibliography now
- Foner (2014). Reconstruction: America's Unfinished Revolution, 1863–1877.

What to add
- The article’s opening could be strengthened by incorporating a concise note about the scale and stakes of Reconstruction-era reforms and constitutional changes, connected to how we think about modern executive power.

Recommended high-quality sources to cite
- Foner (Reconstruction) for the scope and stakes of Reconstruction and for how constitutional structures and civil rights evolved in that era. Publisher/edition details in turn10search1.

How to fit this in the document
- Use Foner to situate Reconstruction as a long-run pressure-test on legitimacy and constitutional arrangements, which can contextualize debates about term limits and impeachment (cite Foner’s updated edition details).
- Add a sentence linking the broad structural shifts of Reconstruction to current debates about presidential power and constitutional rules, with a citation to Foner (updated edition) and a nod to Skowronek’s framing of regime change. ([barnesandnoble.com](https://www.barnesandnoble.com/w/reconstruction-updated-edition-eric-foner/1129142102?utm_source=openai))

Structured recommendations for bibliography edits
- Preserve core, high-quality items already in the bibliography (Foner 2014; Skowronek 2011) but augment with precise, citable corrections:
  - Add: Britannica. Andrew Johnson (impeached but not removed) – to support impeachment correction. ([britannica.com](https://www.britannica.com/biography/Andrew-Johnson?utm_source=openai))
  - Add: U.S. Senate. Impeachment Trial of Andrew Johnson (official trial record). ([senate.gov](https://www.senate.gov/about/powers-procedures/impeachment/impeachment-johnsonandrew.htm?utm_source=openai))
  - Add: National Archives. Impeachment (official history context). ([archives.gov](https://www.archives.gov/legislative/features/impeachment?utm_source=openai))
  - Add: Britannica. Grover Cleveland (two-term nonconsecutive) – to ground the Cleveland example. ([britannica.com](https://www.britannica.com/biography/Grover-Cleveland?utm_source=openai))
  - Add: Yale/Bridges to Skowronek (summaries of his theory for accessibility in the text). ([politicalscience.yale.edu](https://politicalscience.yale.edu/publications/presidential-leadership-political-time-reprise-and-reappraisal-third-edition?utm_source=openai))
  - Add: Foner’s Reconstruction updated edition page (publisher info) to ground the discussion in credible scholarship. ([barnesandnoble.com](https://www.barnesandnoble.com/w/reconstruction-updated-edition-eric-foner/1129142102?utm_source=openai))


Concise editing plan (how to implement)
- Step 1: Correct impeachment and removal inaccuracies
  - Replace Johnson-impeached-but-removed phrasing with Johnson-impeached-but-not-removed; add citations (Britannica; Senate; National Archives). ([britannica.com](https://www.britannica.com/biography/Andrew-Johnson?utm_source=openai))  ([senate.gov](https://www.senate.gov/about/powers-procedures/impeachment/impeachment-johnsonandrew.htm?utm_source=openai)) ([archives.gov](https://www.archives.gov/legislative/features/impeachment?utm_source=openai))
- Step 2: Correct the one-term president never returns claim
  - Introduce Grover Cleveland as a counterexample to the “one-term comeback” claim; add Britannica (and optionally NPR/History.com for accessible narrative). ([britannica.com](https://www.britannica.com/biography/Grover-Cleveland?utm_source=openai))
- Step 3: Introduce theory to frame the narrative
  - Add a short paragraph linking the piece to Skowronek’s “political time” framework; cite Yale and Cambridge for scholarly framing. ([politicalscience.yale.edu](https://politicalscience.yale.edu/publications/presidential-leadership-political-time-reprise-and-reappraisal-third-edition?utm_source=openai))
  - Use Foner to situate Reconstruction as a long-run pressure-test on legitimacy and constitutional arrangements, which can contextualize debates about term limits and impeachment (cite Foner’s updated edition details). ([barnesandnoble.com](https://www.barnesandnoble.com/w/reconstruction-updated-edition-eric-foner/1129142102?utm_source=openai))

Would you like me to draft a revised, citation-annotated version of the opening paragraph and the problematic sentences now, using these sources? I can deliver a compact revision that preserves your voice while correcting the factual points and embedding the new references.""",
            }
        )
    )
    print(response)
