"""Agent for classifying document sections as reference/bibliography sections."""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class SectionClassifierResponse(BaseModel):
    """LLM response for reference section identification."""

    indices: List[int] = Field(
        default_factory=list,
        description="Indices of headings that belong to reference/bibliography sections",
    )


_section_classifier_prompt = ChatPromptTemplate.from_template(
    """Identify which headings BELONG TO reference or bibliography sections.

Headings:
{headings_list}

Rules:
- Return indices of the main reference/bibliography section heading (e.g., "References", "Bibliography")
- ALSO include indices of any artifacts that appear AS headings within the reference section
  (e.g., URLs like "https://..." that got formatted as headings, or malformed entries)
- These artifacts are NOT real section titles - they belong to the reference section above them

Return empty list if no reference section exists."""
)


class SectionClassifierAgent(LangChainAgent):
    """Agent to classify which document headings are reference sections."""

    name = "Section Classifier"
    description = "Identify reference/bibliography sections from document headings"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = SectionClassifierResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> SectionClassifierResponse:
        messages = _section_classifier_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)

