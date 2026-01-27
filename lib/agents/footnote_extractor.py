"""Footnote extraction agent for extracting structured footnotes from text."""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.models.footnote_item import FootnoteItem


class FootnoteExtractorResponse(BaseModel):
    """Response from footnote extraction."""

    footnotes: List[FootnoteItem] = Field(
        default_factory=list,
        description="List of extracted footnotes with marker, text, and reference_code",
    )


_footnote_extractor_prompt = ChatPromptTemplate.from_template(
    """Extract all footnotes from the FOOTNOTE SECTION text.

FOOTNOTE SECTION TEXT:
```
{text}
```

Rules:
- Extract footnotes that follow patterns like: "160. Text content here #footnote-ref-161"
- For each footnote, extract:
  * marker: The footnote number (e.g., "160", "1", "107")
  * text: The full text content of the footnote
  * reference_code: The anchor reference if present (e.g., "#footnote-ref-161")

- Footnotes may span multiple lines - merge them into single entries
- Remove the marker number and reference code from the text field
- Handle various formats: "N. Text", "[N] Text", "^N Text"
- Reference codes are typically at the end: "#footnote-ref-N"
- If no reference code is present, set it to null

Extract ALL footnotes even if they look similar - do not deduplicate.
"""
)


class FootnoteExtractorAgent(LangChainAgent):
    """Agent to extract structured footnotes from text."""

    name = "Footnote Extractor"
    description = "Extract structured footnotes from document text"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = FootnoteExtractorResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> FootnoteExtractorResponse:
        messages = _footnote_extractor_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
