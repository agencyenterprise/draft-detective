# %%
"""

Categorizes claims from research documents into predefined categories.

Each claim is analyzed to determine:
- Category (using a 6-category taxonomy)
- Rationale for the categorization
- Whether external verification is needed

The agent uses structured outputs via Pydantic models to ensure consistent
and validated responses that can be reliably processed downstream.

The categories are:
- Established/reported knowledge
- Methodology/procedural
- Empirical/analytical results
- Inferential/interpretive claims
- Meta/structural/evaluative
- Other

"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.models import ClaimCategory
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema

# =========================
#  Pydantic data contracts
# =========================


class ClaimCategorizationResponse(BaseModel):
    claim: str = Field(description="Exact claim text as analyzed.")
    claim_category: ClaimCategory = Field(description="Assigned category.")
    rationale: str = Field(
        description="Reason for the category assignment and for the needs_external_verification decision. Maximum two sentences."
    )
    needs_external_verification: bool = Field(
        description=(
            "True ONLY if the claim asserts a specific factual statement from external sources "
            "that is NOT common knowledge and CAN be verified by external sources. "
            "False for: common knowledge, authors' own work/results, inferences, "
            "interpretations, structural statements, or claims that cannot be externally verified. "
            "IMPORTANT: When uncertain, default to FALSE."
        ),
    )


class ClaimCategorizationResponseWithClaimIndex(ClaimCategorizationResponse):
    chunk_index: int
    claim_index: int


_claim_categorizer_prompt = ChatPromptTemplate.from_template(
    """
You are an expert claim categorizer. Your task is to tag the specific claim in a passage
with ONE of SIX categories and to determine if it needs EXTERNAL VERIFICATION.

## Decision Framework for Claim Category Assignment:

STEP 1: Check for Meta/Structural/Evaluative (Category 5)
- Does the claim describe the document's organization, structure, or navigation?
  → Phrases: "in the next section", "in the following section", "this paper", "we discuss"
- Does it evaluate the work's significance, novelty, or contribution?
  → Phrases: "this study represents", "significant improvement", "novel contribution"
- Does it describe limitations, scope, or goals of THIS work?
  → If YES → Category 5: Meta/Structural/Evaluative
  → If NO → Continue to STEP 2

STEP 2: Check for Inferential/Interpretive (Category 4)
- Does the claim interpret, explain, or draw conclusions from results?
  → Phrases: "suggests", "implies", "indicates", "supports", "argues", "may indicate"
- Does it propose causality, mechanisms, or theoretical explanations?
- Does it make inferences from earlier statements in the document?
- Is it an opinion, evaluation, or interpretation rather than a fact?
  → If YES → Category 4: Inferential/Interpretive
  → If NO → Continue to STEP 3

STEP 3: Check for Empirical/Analytical Results (Category 3)
- Does the claim report NEW findings, measurements, or results from THIS work?
  → Phrases: "we found", "improved by", "reached", "measured", "discovered"
- Does it describe quantitative outcomes, error rates, or patterns from analysis?
- Is it a result that came from the authors' own experiments, analysis, or calculations?
  → If YES → Category 3: Empirical/Analytical Results
  → If NO → Continue to STEP 4

STEP 4: Check for Methodological/Procedural (Category 2)
- Does the claim describe WHAT the authors did or HOW they did it?
  → Phrases: "we used", "we followed", "we collected", "we analyzed", "we applied"
- Does it describe methods, algorithms, instruments, data sources, or procedures?
- Does it describe the methodology, techniques, or approach used in THIS paper?
  → If YES → Category 2: Methodological/Procedural
  → If NO → Continue to STEP 5

STEP 5: Check for Established/Reported Knowledge (Category 1)
- Does the claim report background knowledge, prior research, or established facts?
- Does it cite or reference external sources, prior studies, or field knowledge?
- Is it providing context, definitions, or anchoring information from outside this paper?
- Does it describe what others have found or what is known in the field?
  → If YES → Category 1: Established/Reported Knowledge
  → If NO → Continue to STEP 6

STEP 6: Other (Category 6)
- Only use if the claim doesn't fit any of the above categories
- This should be rare - most claims should fit into categories 1-5

## Key Distinctions to Avoid Common Mistakes:

### Category 1 vs Category 3:
- Category 1: "Previous studies showed X" (external knowledge)
- Category 3: "We found X" (this paper's results)

### Category 2 vs Category 3:
- Category 2: "We used method X" (how they did it)
- Category 3: "Method X improved accuracy by 10%" (what they found)

### Category 3 vs Category 4:
- Category 3: "We found a correlation of 0.8" (factual result)
- Category 4: "This correlation suggests causation" (interpretation)

### Category 1 vs Category 4:
- Category 1: "Smith et al. (2020) found that X causes Y" (reporting external finding)
- Category 4: "This finding supports the theory that X causes Y" (interpreting/connecting)

## Context-Aware Decision Making:

- Use the document summary to understand what is "new" vs "background"
  → New findings → Category 3
  → Background/context → Category 1

- Check if the claim describes the authors' own work
  → Own methodology → Category 2
  → Own results → Category 3
  → Own interpretation → Category 4

- Look for temporal indicators
  → "Previous studies", "Prior work" → Category 1
  → "We found", "Our results" → Category 3
  → "This suggests", "This implies" → Category 4

## Decision Priority Order:

When a claim could fit multiple categories, use this priority:
1. Meta/Structural/Evaluative (if it's about the document structure)
2. Inferential/Interpretive (if it's an interpretation)
3. Empirical/Analytical Results (if it's a new finding)
4. Methodological/Procedural (if it's about methods)
5. Established/Reported Knowledge (if it's background/prior work)
6. Other (only as last resort)

## Common Edge Cases:

**"We compared our results to Smith et al. (2020)"**
→ Category 3 (reporting own results, even if comparing)

**"Following Smith et al. (2020), we used method X"**
→ Category 2 (describing methodology, even if citing external method)

**"This result is consistent with Smith et al. (2020)"**
→  Category 3 (reporting own results, even if comparing)

**"Smith et al. (2020) found that X causes Y"**
→ Category 1 (reporting external knowledge)

**"Our finding that X causes Y supports the theory proposed by Smith et al. (2020)"**
→ Category 4 (interpretive claim connecting own work to prior theory)

## Decision Framework for needs_external_verification:

STEP 1: Check category first
- If category is "Inferential/Interpretive" → ALWAYS FALSE
- If category is "Meta/Structural/Evaluative" → ALWAYS FALSE
- If category is "Empirical/Analytical Results" → Usually FALSE (only TRUE if comparing to external work)

STEP 2: For other categories, check if it's generally accepted knowledge or inferred knowledge
- Could this be a generally accepted claim in the subject domain of the document? → FALSE
- Is this basic terminology, definition, or fundamental principle? → FALSE
- Is this a logical inference from already-cited material? → FALSE

STEP 3: Check if it's the authors' own work
- Is this describing methodology/results from THIS paper? → FALSE
- Is this a conclusion drawn from THIS paper's analysis? → FALSE

STEP 4: Only then check if external verification is needed
- Does it assert a specific factual claim from external sources? → TRUE
- Does it compare to specific external findings? → TRUE
- Are there citations within the same sentence? → TRUE
- Is it a contested or debatable assertion presented as fact? → TRUE

DEFAULT: When in doubt, set to FALSE. Only set to TRUE if the claim clearly requires external verification.

### Context-Aware Decision Making:

- Check if the claim builds on earlier cited material in the same paragraph → Usually FALSE
- Check if the claim describes the authors' own methodology/results → FALSE
- Check if similar claims earlier in the document were already substantiated → May be FALSE
- Use the document summary to understand what is "new" vs "background" → New findings = FALSE


### Claims that typically do not require external verification:

- Common knowledge claims
    - Basic definitions and terminology
    - General statistical trends that are widely reported and uncontroversial
    - Standard definitions and terminology established in the field
    - Basic geographic, demographic, or institutional facts readily available in reference sources
    - Basic historical dates and events that are undisputed
    - Well-established facts or general principles widely accepted in the field and appearing across multiple authoritative sources
    - Fundamental principles or theories in the domain that are universally accepted by practitioners
    - Counter Examples: Statements that are counter to generally accepted knowledge in the domain or opinions that require evidence to support.
        - "Machine learning has generally few harmful consequences in society."
        - "It is known that the US's military excursions in the 50s and 60s were widely supported by the public."
- Inferences that do not require external references
    - Conjectural statements that use words like "might", "could", and "can" that cannot be verified by external sources
    - Opinions, interpretations, or evaluations
    - Logical deductions or inferences that follow clearly from stated premises
    - Inferential continuity: claims that clearly and logically follow from earlier substantiated statements in the same paragraph or nearby context
    - Analytic or hypothetical reasoning: "If X, then Y" constructions that build on established evidence without asserting new factual data
- Hypotheticals
    - Scenario illustration: hypothetical examples or thought experiments used to illustrate a risk, mechanism, or consequence already supported by cited claims
- Structural
    - Statements describing the structure or scope of the work itself that report on the authors' own methodology, goals, or organization rather than asserting an external fact

### CRITICAL: Conservative Default Rule

The default for needs_external_verification should be FALSE. Only set to TRUE if you are confident that:
1. The claim asserts a specific factual statement from external sources
2. It is NOT common knowledge for the subject domain of the document
3. It CAN be verified by external sources
4. It is NOT the authors' own work, inference, or interpretation

When in doubt between TRUE and FALSE, default to FALSE.
---

# Output Requirements
- Return one JSON object matching the schema exactly.
- Each claim must have exactly one category and a short-sentence rationale.
- The needs_external_verification field should be set to TRUE if the claim requires external verification, and FALSE otherwise.

{domain_context}

{audience_context}

## Summary of the document (for context about the document's main argument)
```
{document_summary}
```

## The paragraph of the original document that contains the chunk of text that we want to substantiate
```
{paragraph}
```

## The chunk of text from the original document that contains the claim to be substantiated
```
{chunk}
```

## The claim that is inferred from the chunk of text. This is the claim that we want to categorize.
```
{claim}
```
"""
)


class ClaimCategorizerAgent(LangChainAgent):
    name = "Claim Categorizer"
    description = "Categorize a claim into one of the six categories"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = ClaimCategorizationResponse

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> ClaimCategorizationResponse:
        messages = _claim_categorizer_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    from lib.config.env import config

    nest_asyncio.apply()
    # Test cases with expected vs inferred categorizations
    test_cases = [
        {
            "domain_context": "Military personnel management and technology",
            "audience_context": "Military leadership and HR professionals",
            "document_summary": """In recent years, RAND Project AIR FORCE (PAF) has supported the U.S. Air Force's efforts to enhance its talent management practices through technology investments (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022). These projects demonstrate that leveraging emerging technology can transform the USAF's talent management system. Beyond conceptual work, PAF developed a prototype tool, Personnel Records Scoring System (PReSS), and tested it with select DTs. In this report, we describe improvements to PReSS and an expansion to enlisted personnel.""",
            "paragraph": """In recent years, RAND Project AIR FORCE (PAF) has supported the U.S. Air Force's efforts to enhance its talent management practices through technology investments (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022). These projects demonstrate that leveraging emerging technology can transform the USAF's talent management system.""",
            "chunk": chunk,
            "claim": claim,
            "expected_category": expected,
            "expected_needs_verification": needs_verification,
        }
        for chunk, claim, expected, needs_verification in [
            # Test case 1: Established knowledge requiring citation since not universally accepted
            (
                "RAND Project AIR FORCE (PAF) has supported the U.S. Air Force's efforts and there is a past history of developing technology to support talent management (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022)",
                "RAND Project AIR FORCE (PAF) has supported the U.S. Air Force's efforts and there is a past history of developing technology to support talent management (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022)",
                ClaimCategory.ESTABLISHED,
                True,
            ),
            # Test case 2: Methodology/procedural - description of what was done, original to this work
            (
                "PAF developed a prototype tool, Personnel Records Scoring System (PReSS) by leveraging existing technology and data sources",
                "PAF developed a prototype tool, Personnel Records Scoring System (PReSS) by leveraging existing technology and data sources",
                ClaimCategory.METHODOLOGY,
                False,
            ),
            # Test case 3: Empirical/analytical results (original findings presented by authors), no citation needed
            (
                "PAF tested PReSS with select DTs and found that it was 20 percent more effective in improving the USAF's talent management system than the baseline",
                "PAF tested PReSS with select DTs and found that it was 20 percent more effective in improving the USAF's talent management system than the baseline",
                ClaimCategory.RESULTS,
                False,
            ),
            # Test case 4: Inferential/interpretive (drawing a conclusion from methods/results), occasionally requires citation but not here as it's a direct inference
            (
                "These projects demonstrate that leveraging technology can transform talent management",
                "These projects demonstrate that leveraging technology can transform talent management",
                ClaimCategory.INTERPRETATION,
                False,
            ),
            # Test case 5: Meta/structural statement (about document structure/content), rarely requires citation
            (
                "In this report, we describe improvements to PReSS",
                "In this report, we describe improvements to PReSS",
                ClaimCategory.META,
                False,
            ),
            # Test case 6: Established/reported knowledge with explicit citations (external knowledge), always needs verification
            (
                "It has been shown that technology investments (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022) can transform the USAF's talent management system",
                "It has been shown that technology investments (Schulker et al., 2022; Snyder, 2022; Yeung et al., 2022) can transform the USAF's talent management system",
                ClaimCategory.ESTABLISHED,
                True,
            ),
            # Test case 7: Methodology detail (testing process described, original to authors)
            (
                "As additional tests, the method was extended to an eigenvalue analysis in order to explore whether additional factors are important in predicting the effectiveness of the PReSS system",
                "As additional tests, the method was extended to an eigenvalue analysis in order to explore whether additional factors are important in predicting the effectiveness of the PReSS system",
                ClaimCategory.METHODOLOGY,
                False,
            ),
            # Test case 8: Empirical result (new information generated within the work, no comparison to external findings)
            (
                "The eigenvalue analysis found that the additional factors were not important in predicting the effectiveness of the PReSS system",
                "The eigenvalue analysis found that the additional factors were not important in predicting the effectiveness of the PReSS system",
                ClaimCategory.RESULTS,
                False,
            ),
            # Test case 9: Inferential claim making broader theoretical conclusion, cites no external work
            (
                "This suggests that advanced mathematical methods can be used to predict the effectiveness of the PReSS system, but they don't appear to be necessary",
                "This suggests that advanced mathematical methods can be used to predict the effectiveness of the PReSS system, but they don't appear to be necessary",
                ClaimCategory.INTERPRETATION,
                False,
            ),
            # Test case 10: Use 'other' only if none above fit; this is a catch-all for edge or ambiguous statements, still requires verification if asserted as fact
            (
                "National Institute of Standards and Technology (NIST); Pentagoin (2022); etc.",
                "National Institute of Standards and Technology (NIST); Pentagoin (2022); etc.",
                ClaimCategory.OTHER,
                True,
            ),
        ]
    ]

    from lib.services.file_artifacts_service.mock import MockFileArtifactsService

    context = ContextSchema(
        openai_api_key=config.OPENAI_API_KEY,
        vector_store=None,
        file_artifacts_service=MockFileArtifactsService(),
    )
    claim_categorizer_agent = ClaimCategorizerAgent(context)

    # Run tests and compare results
    for i, test_case in enumerate(test_cases, 1):
        response = asyncio.run(claim_categorizer_agent.ainvoke(test_case))

        print(f"\nTest Case {i}:")
        print(f"Claim: {test_case['claim']}")
        print(f"Expected Category: {test_case['expected_category']}")
        print(f"Inferred Category: {response.claim_category}")
        print(
            f"Expected Needs Verification: {test_case['expected_needs_verification']}"
        )
        print(f"Inferred Needs Verification: {response.needs_external_verification}")
        print(
            f"Match: {test_case['expected_category'] == response.claim_category and test_case['expected_needs_verification'] == response.needs_external_verification}"
        )
