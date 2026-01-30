"""
Author Name Extractor Agent

Extracts the author's full name and token positions from an author bio.
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class AuthorNameResponse(BaseModel):
    """Response from name extraction."""

    name: str = Field(description="The author's full name")
    positions: List[int] = Field(
        default_factory=list,
        description="0-indexed token positions of the name in the text",
    )


_extraction_prompt = ChatPromptTemplate.from_template(
    """You are analyzing an author biography to extract the author's name.

## Tokenized Author Bio (positions are 0-indexed)
{tokenized_text}

## Instructions
1. Identify the author's FULL NAME (first and last name, middle name if present)
2. Return the token positions (0-indexed) that make up the name
3. The name is typically at the very beginning of the bio

## Example
Input: [{{"token": "John", "position": 0}}, {{"token": "Smith", "position": 1}}, {{"token": "is", "position": 2}}, ...]
Output: name="John Smith", positions=[0, 1]
"""
)


class AuthorNameExtractorAgent(LangChainAgent):
    """Agent that extracts author name and token positions from bio text."""

    name = "Author Name Extractor"
    description = "Extract author name and token positions from biography"
    model = gpt_5_mini_model
    temperature = 0.1
    output_schema = AuthorNameResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> AuthorNameResponse:
        """Extract author name from bio text.

        Expected prompt_kwargs:
            - author_text: str (the full author bio text)
        """
        author_text = prompt_kwargs["author_text"]

        # Tokenize with 0-based indices
        tokens = author_text.split()
        tokenized = [{"token": t, "position": i} for i, t in enumerate(tokens)]

        messages = _extraction_prompt.format_messages(tokenized_text=str(tokenized))
        result = await self.llm.ainvoke(messages, config=config)

        return result
