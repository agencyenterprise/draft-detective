from typing import Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class Claim(BaseModel):
    """A single factual claim with verification properties."""

    text: str = Field(
        description="The relevant part of the text within the chunk of text that is being decomposed into claims."
    )

    claim: str = Field(description="The claim made in the text")

    rationale: str = Field(
        description="The rationale for why you think the chunk of text implies this claim"
    )
    central: bool = Field(
        description="Whether the claim is central to the argument of the document"
    )
    centrality_rationale: Optional[str] = Field(
        default=None,
        description="The rationale for why you think the claim is central or is not central to the argument of the document",
    )


class ClaimResponse(BaseModel):
    claims: list[Claim] = Field(
        description="A list of claims made in the chunk of text"
    )
    rationale: str = Field(
        description="Overall rationale for why you think the chunk of text implies these claims"
    )


class ClaimResponseWithChunkIndex(ClaimResponse):
    chunk_index: int = Field(
        description="The index of the chunk of text that contains the claim"
    )


_claim_extractor_prompt_claimify = ChatPromptTemplate.from_template(
    """
### Agent Setup and Terms
You are an assistant for a group of fact-checkers. You will be given the summarized argument of a document, a paragraph from a document, and a chunk of text (typically a sentence or a few sentences) from that paragraph, and your task is to extract all the claims from the chunk of text and determine if they are central to the document's summarized argument.

Claim (definition): An assertion or proposition that is made within a chunk of text. Grammatically, a sentence that expresses a claim is a declarative sentence and thus contains a verb.

True Examples of Claims:
- "Quantum gravity is a theory that combines quantum mechanics and general relativity" (Statement/description of a theory)
- "Developments in neural networks has accelerated the economic divide between first and third world countries" (Statement/description of a fact)
- "The United States has the highest GDP in the world" (Statement/description of a fact)

Non-Examples of Claims:
- "The Space Time Approach to Quantum Gravity" (This is a title of a paper, not a claim)
- "Johnson, J. (2024) Economic consequences of developing neural networks" (This is a reference, not a claim)


### Task
Your task is to identify all specific propositions in the sentence and ensure that each proposition is decontextualized AND to identify if the proposition is central to the argument of the paper.

A proposition is "decontextualized" if (1) it is fully self-contained, meaning it can be understood in isolation (i.e., without the question, the context, and the other propositions), AND (2) its meaning in isolation matches its meaning when interpreted alongside the question, the context, and the other propositions. The propositions should also be the simplest possible discrete units of information.

A proposition is central to the argument of a paper if the invalidity or falseness of the claim could weaken the argument of the paper.

Note the following rules:
- If the chunk of text is a bibliographic entry (usually found in references or bibliography sections, indicated by headings like "References", "Bibliography", "Works Cited"), do not consider it as having claims.
- Sometimes a specific claim is buried in a sentence that is mostly generic or unverifiable. For example, "John's notable research on neural networks demonstrates the power of innovation" contains the specific claim "John has research on neural networks". Another example is "TurboCorp exemplifies the positive effects that prioritizing ethical considerations over profit can have on innovation" where the specific claim is "TurboCorp prioritizes ethical considerations over profit".
- Do NOT repeat the same claim in the list of claims.
- Do NOT use any external knowledge beyond what is stated in the paragraph and chunk of text.

Each proposition must be:
- Specific: It should refer to particular entities, events, or relationships
- Decontextualized: It should be understandable without additional context

Important rules:
- If a sentence has multiple adjectives/modifiers describing the same entity, you should include all those adjectives/modifiers in the same claim.
- Do NOT repeat the same claim in the list of claims.
- Do NOT use any external knowledge beyond what is stated in the paragraph and chunk of text
- Each fact-checker will only have access to one claim - they will not have access to the paragraph and other claims
- Do not classify something as a claim if it cannot be decontextualized (i.e., it cannot be understood or verified in isolation without additional context from the document)
- If there are no specific claims in the chunk of text, return an empty list of claims.
- Do NOT extract claims from sections that are about the document itself. This means don't extract claims concerning funding, acknowledgments, or the "about" section of the report. Only extract from the main analysis content. Use the headings context to determine the section of the chunk.

### Output Structure

For the final claims, you must create structured objects with:
- rationale: The rationale for why you think the chunk of text implies this list of claims
- list of claims: The list of claims made in the chunk of text

Within the list of claims, you must include the following information for each claim:
- text: The relevant part of the text within the chunk of text that implies the claim
- claim: The claim text
- rationale: The rationale for why you think the chunk of text implies this claim
- central: Whether the claim is central to the argument of the document
- centrality_rationale: The rationale for why you think the claim is central or is not central to the argument of the document.

# Agent Inputs

{domain_context}

{audience_context}

{summary_context}

{headings_context}

## The paragraph of the original document that contains the chunk of text that we want to analyze
```
{paragraph}
```

## The chunk of text to extract claims from
```
{chunk}
```
"""
)


class ClaimExtractorAgent(LangChainAgent):
    name = "Claim Extractor"
    description = "Extract claims from a chunk of text"
    model = gpt_5_mini_model
    temperature = 0.5
    output_schema = ClaimResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ClaimResponse:
        messages = _claim_extractor_prompt_claimify.format_messages(**prompt_kwargs)
        return cast(
            ClaimResponse,
            await self.llm.ainvoke(messages, config=config),
        )
