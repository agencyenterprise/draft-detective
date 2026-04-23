from typing import Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_model
from lib.models.agent import LangChainAgent


class ClaimCommonKnowledgeResult(BaseModel):
    needs_substantiation: bool = Field(
        description="A boolean value indicating whether the claim needs to be substantiated."
    )
    rationale: str = Field(
        description="A brief explanation for why this claim needs to or does not need to be substantiated by references/evidence",
    )
    guiding_rules: str = Field(
        default="",
        description="Which rule(s) from the instructions most strongly guided your judgment and why",
    )


class ClaimCommonKnowledgeResultWithClaimIndex(ClaimCommonKnowledgeResult):
    chunk_index: int
    claim_index: int


_claim_needs_substantiation_checker_prompt = ChatPromptTemplate.from_template(
    """
You are an expert academic reviewer for a scientific research paper. Your task is to analyze a claim in the manuscript and determine whether the claim needs to be substantiated by references and/or evidence or not. Approach this review as an impartial subject-matter expert, providing constructive and detailed feedback.

You will be given the full document, a chunk of text from the document and a claim that is inferred from that chunk of text.

## Claim evaluation criteria

When assessing a claim, prioritize evidence and reasoning contained within or near the chunk. The full document may be consulted only to verify whether the claim’s logic or evidentiary base has already been established earlier.

### Claims that require substantiation:

1. Specific research findings or data points from studies, surveys, or analyses
2. Expert opinions or interpretations not universally held in the field
3. Recent developments or trends not yet widely established
4. Comparative analyses or rankings between entities, programs, or policies
5. Quantitative claims with specific numbers, percentages, or measurements
6. Policy recommendations or normative statements about what should be done
7. Contested or debatable assertions that are presented as factual or predictive claims, not as hypothetical scenarios or logical extrapolations

### Claims that do not require substantiation:

1. Well-established facts or general principles widely accepted in the field and appearing across multiple authoritative sources
2. Basic definitions and terminology
3. Basic historical dates and events that are undisputed (e.g., major wars, founding dates)
4. Fundamental principles or theories in the domain that are universally accepted by practitioners
5. General statistical trends that are widely reported and uncontroversial
6. Standard definitions and terminology established in the field
7. Basic geographic, demographic, or institutional facts readily available in reference sources
8. Logical deductions that follow clearly from stated premises
9. Common knowledge that domain experts would not question
10. Statements describing the structure or scope of the work itself that report on the authors’ own methodology, goals, or organization rather than asserting an external fact
11. Inferential continuity: claims that clearly and logically follow from earlier substantiated statements in the same paragraph or nearby context (e.g., describing implications, extrapolations, or risk scenarios grounded in prior cited material)
12. Analytic or hypothetical reasoning: "If X, then Y" constructions that build on established evidence without asserting new factual data
13. Scenario illustration: hypothetical examples or thought experiments used to illustrate a risk, mechanism, or consequence already supported by cited claims

### Additional Guidelines

- Do not flag claims as needing substantiation if they are not central arguments of the paper, but rather peripheral or supporting arguments and can still be reasonably considered common knowledge
- When uncertainty remains about whether a claim introduces new information, assume it does not. The threshold for requiring substantiation should be conservative: only flag when the absence of evidence would materially weaken the credibility or accuracy of the claim for a domain expert
- Do not flag causal or consequential phrasing (e.g., “could cause,” “might lead to”) if it appears in hypothetical, illustrative, or scenario-based reasoning. Treat such statements as speculative analysis unless the author presents them as established or empirically supported facts
- The perceived scale, severity, or policy impact of a statement should not by itself trigger a need for substantiation. Focus strictly on whether it asserts new factual content rather than hypothetical or inferential reasoning
- When explaining your decision, clearly identify (a) whether the claim introduces new information or extends existing reasoning, and (b) which rule(s) from the framework guided your judgment

{domain_context}

{audience_context}

## The original document from which we are substantiating claims within a chunk
```
{full_document}
```

## The paragraph of the original document that contains the chunk of text that we want to substantiate
```
{paragraph}
```

## The chunk of text from the original document that contains the claim to be substantiated
```
{chunk}
```

## The claim that is inferred from the chunk of text to be substantiated
```
{claim}
```
"""
)


class ClaimNeedsSubstantiationCheckerAgent(LangChainAgent):
    name = "Claim Needs Substantiation Checker"
    description = (
        "Check if a claim needs to be substantiated or not (common knowledge etc)"
    )
    model = gpt_5_model
    temperature = 0.2
    output_schema = ClaimCommonKnowledgeResult

    async def ainvoke(
        self, prompt_kwargs: dict, config: Optional[RunnableConfig] = None
    ) -> ClaimCommonKnowledgeResult:
        messages = _claim_needs_substantiation_checker_prompt.format_messages(
            **prompt_kwargs
        )
        return cast(
            ClaimCommonKnowledgeResult,
            await self.llm.ainvoke(messages, config=config),
        )
