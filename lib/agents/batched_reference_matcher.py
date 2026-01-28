"""Agent for matching multiple references to documents in a single LLM call.

Part of the two-stage reference matching approach:
- Stage 1: Embedding-based candidate retrieval (ReferenceEmbeddingMatcher)
- Stage 2: This agent - LLM verification of candidates in batches
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.document_summarizer import DocumentSummary
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.services.reference_embedding_matcher import CandidateMatch

REFERENCES_PER_BATCH = 5
MAX_CANDIDATES_PER_REF = 15


class SingleReferenceMatch(BaseModel):
    """Match result for a single reference within a batch."""

    reference_index: int = Field(
        description="0-based index of the reference within the batch (0, 1, 2, ...)"
    )
    matched_candidate: str = Field(
        description="Letter of matched candidate (A, B, C, ...) or 'NONE' if no match"
    )
    confidence: str = Field(description="Confidence level: high, medium, low, or none")
    reasoning: str = Field(description="Brief explanation for the match decision")


class BatchedMatchResult(BaseModel):
    """Results from matching a batch of references."""

    matches: List[SingleReferenceMatch] = Field(
        description="Match results for each reference in the batch"
    )


def format_candidate(letter: str, summary: DocumentSummary) -> str:
    """Use letters (A, B, C) for unambiguous LLM output parsing."""
    return (
        f"  {letter}. Title: {summary.title} | "
        f"Authors: {summary.authors} | "
        f"Year: {summary.publication_date}"
    )


def format_batch_prompt(
    reference_texts: List[str],
    candidates_per_ref: List[List[CandidateMatch]],
) -> str:
    """Group refs with their candidates to reduce LLM calls (5 refs per call vs 1)."""
    sections = []

    for ref_idx, (ref_text, candidates) in enumerate(
        zip(reference_texts, candidates_per_ref)
    ):
        section = f'Reference {ref_idx}: "{ref_text}"\n'
        section += f"Candidates for Reference {ref_idx}:\n"

        if candidates:
            for cand_idx, candidate in enumerate(candidates[:MAX_CANDIDATES_PER_REF]):
                letter = chr(ord("A") + cand_idx)
                section += format_candidate(letter, candidate.summary) + "\n"
        else:
            section += "  (No candidates available)\n"

        sections.append(section)

    return "\n".join(sections)


_batched_reference_matcher_prompt = ChatPromptTemplate.from_template(
    """You are matching bibliographic references to documents. You will be given multiple references, each with a set of candidate documents.

For EACH reference, determine which candidate (if any) it cites.

## Matching Guidelines:
1. Compare author names - last names are most important, "et al." abbreviations are valid
2. Compare titles - look for exact or very similar matches (case-insensitive)
3. Consider publication year if mentioned in the reference
4. References may use abbreviated titles or different formatting
5. Only match if you are reasonably confident the reference cites that specific document
6. If none of the candidates match, return "NONE"

## References and Candidates:

{batch_content}

## Output Instructions:
For each reference (0 through {max_index}), provide:
- reference_index: The reference number (0, 1, 2, ...)
- matched_candidate: The letter of the matching candidate (A, B, C, ...) or "NONE"
- confidence: "high", "medium", "low", or "none"
- reasoning: Brief explanation (1-2 sentences)

Return results for ALL references in the batch.
"""
)


class BatchedReferenceMatcherAgent(LangChainAgent):
    """Batch multiple references per LLM call to reduce API costs and latency.

    Why batching: Single-ref calls create N API round-trips. Batching 5 refs
    per call reduces overhead 5x while staying within context limits.
    """

    name = "Batched Reference Matcher"
    description = "Match multiple bibliographic references to their candidate documents in a single call"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = BatchedMatchResult

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> BatchedMatchResult:
        messages = _batched_reference_matcher_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)

    async def match_batch(
        self,
        reference_texts: List[str],
        candidates_per_ref: List[List[CandidateMatch]],
        config: Optional[RunnableConfig] = None,
    ) -> BatchedMatchResult:
        """Convenience wrapper that handles prompt formatting."""
        batch_content = format_batch_prompt(reference_texts, candidates_per_ref)
        max_index = len(reference_texts) - 1

        return await self.ainvoke(
            {"batch_content": batch_content, "max_index": max_index},
            config=config,
        )
