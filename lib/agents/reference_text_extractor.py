"""Reference extraction agent for extracting bibliographic items from text."""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class ReferenceTextExtractorResponse(BaseModel):
    """Response from reference extraction."""

    references: List[str] = Field(
        default_factory=list,
        description="List of extracted reference texts",
    )


_reference_extractor_prompt = ChatPromptTemplate.from_template(
    """Extract all bibliographic references from the CURRENT TEXT section only.

CURRENT TEXT (extract references from here):
```
{text}
```

Rules:
- Return each reference as a single clean string
- Remove entry numbers (e.g., [1], 1., (1))
- Preserve author names, titles, publication details, years, URLs, DOIs
- Merge multi-line references into single lines
- Skip non-reference content
- If you see a placeholder for repeated authors at the start of a reference (commonly `---.` but also `———.`, `___`, or similar patterns), replace it with the author from the last reference in PREVIOUS REFERENCES

Extract ALL refs even if they look similar:
- Same author with different titles → extract BOTH
- Same organization with different publications → extract BOTH  
- Numbered variants (undated-a, undated-b, undated-c, 2024a, 2024b) → extract ALL
- Cross-references like "NASA—See National Aeronautics..." → extract as written
- Do NOT deduplicate - that happens later in the pipeline

PREVIOUS REFERENCES (already extracted, use for context only):
```
{previous_context}
```"""
)


class ReferenceTextExtractorAgent(LangChainAgent):
    """Agent to extract bibliographic references from text."""

    name = "Reference Extractor"
    description = "Extract bibliographic references from document text"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = ReferenceTextExtractorResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> ReferenceTextExtractorResponse:
        if "previous_context" not in prompt_kwargs:
            prompt_kwargs["previous_context"] = "(none - this is the first window)"
        messages = _reference_extractor_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
