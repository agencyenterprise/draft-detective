from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class BibliographyItem(BaseModel):
    text: str = Field(description="The text of the bibliographic item")
    has_associated_supporting_document: bool = Field(
        description="A boolean value indicating whether the bibliographic item has an associated supporting document provided by the user"
    )
    index_of_associated_supporting_document: int = Field(
        description="If the bibliographic item has an associated supporting document, this will be the index of the supporting document in the list of supporting documents provided by the user (index starts at 1), otherwise it will be -1."
    )
    name_of_associated_supporting_document: str = Field(
        description="If the bibliographic item has an associated supporting document, this will be the name of the supporting document, otherwise it will be an empty string."
    )


class ReferenceExtractorResponse(BaseModel):
    references: list[BibliographyItem] = Field(
        description="A list of bibliographic items found in the document"
    )


_reference_extractor_prompt = ChatPromptTemplate.from_template(
    """
# Task
You are a reference extractor. You are given an academic paper text and you need to extract any bibliographic items used in that text.
- References are usually found in the bibliography section at the end of the paper.
- If there are no references used in the text, return an empty list.
- Preserve the original bibliographic item textual and markdown content as much as possible, including formatting tags; do not include the entry number if there is one; remove unneeded escape characters; remove new lines in the middle of a bibliographic item.
- Ignore footnotes that might exist in the bibliography section.

For each bibliographic item, you need to return the following information:
- The text of the bibliographic item
- A boolean value indicating whether the bibliographic item has an associated supporting document provided by the user
- The index of the supporting document in the list of supporting documents provided by the user, if any

## The text to extract bibliographic items from
```
{full_document}
```

## The supporting documents provided by the user
{supporting_documents}
"""
)


class ReferenceExtractorAgent(LangChainAgent):
    name = "Reference Extractor"
    description = "Extract bibliographic items from a document"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = ReferenceExtractorResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> ReferenceExtractorResponse:
        messages = _reference_extractor_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
