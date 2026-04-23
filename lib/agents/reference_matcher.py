"""Agent for matching bibliographic references to documents."""

from typing import Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class ReferenceMatchResult(BaseModel):
    """Result of matching a reference to documents."""

    matched_index: int = Field(
        description="1-based index of matched document, or -1 if no match"
    )
    confidence: str = Field(description="Confidence level: high, medium, low, or none")
    reasoning: str = Field(description="Brief explanation for the match decision")


_reference_matcher_prompt = ChatPromptTemplate.from_template(
    """You are matching bibliographic references to documents. Given a reference citation text, determine which document (if any) it cites.

## Reference to match:
"{reference_text}"

## Available documents:
{candidates}

## Instructions:
1. Compare the reference against each document's title, authors, and year
2. Look for matching author names (last names are most important)
3. Look for matching or similar titles
4. Consider the publication year if mentioned
5. A reference may use abbreviated titles or "et al." for multiple authors

Return the number of the matching document (1, 2, 3, etc.) or -1 if none match.
Only return a match if you are reasonably confident the reference cites that specific document.
"""
)


class ReferenceMatcherAgent(LangChainAgent):
    """Agent to match bibliographic references to supporting documents."""

    name = "Reference Matcher"
    description = "Match bibliographic references to supporting documents using title, author, and year comparison"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = ReferenceMatchResult

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ReferenceMatchResult:
        messages = _reference_matcher_prompt.format_messages(**prompt_kwargs)
        return cast(
            ReferenceMatchResult,
            await self.llm.ainvoke(messages, config=config),
        )
