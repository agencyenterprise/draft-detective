from enum import Enum
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class CitationType(str, Enum):
    BIBLIOGRAPHY = "bibliography"
    URL = "url"
    FOOTNOTE = "footnote"
    OTHER = "other"


class Citation(BaseModel):
    text: str = Field(
        description="The text of the citation or footnote mark, e.g., [1] or (Doe, et al., 2025), a url, etc. The bibliography/footnote itself is not a citation."
    )
    type: CitationType = Field(
        description="The type of the citation. This should be a value from the CitationType enum."
    )
    format: str = Field(
        description="The format of the citation or footnote mark, e.g., [number] or (Name, et al., Year), url, etc."
    )
    needs_bibliography: bool = Field(
        description="A boolean value indicating whether the citation refers to a bibliography entry or footnote in the document so it expected to have an associated bibliography entry or footnote"
    )
    associated_bibliography: str = Field(
        description="If the document includes a bibliography entry related to this citation, this will be an exact copy of that bibliography entry (do not include the entry number if there is one, just the full context of the bibliography entry), otherwise it will be an empty string."
    )
    index_of_associated_bibliography: int = Field(
        description="The index of the bibliography entry that this citation refers to, if any. Indices start at 1. If the citation does not refer to a bibliography entry, this should be -1."
    )
    rationale: str = Field(
        description="A very brief rationale for why you think this text is a citation"
    )


class CitationResponse(BaseModel):
    citations: list[Citation] = Field(
        description="A list of citations found in the chunk of text"
    )
    rationale: str = Field(
        description="Very brief rationale for why you think the chunk of text includes these citations, if any"
    )


class CitationResponseWithChunkIndex(CitationResponse):
    chunk_index: int = Field(
        description="The index of the chunk of text that contains the citations"
    )


_citation_detector_prompt = ChatPromptTemplate.from_template(
    """
## Task
You are a citation detector. You are given a chunk of text and you need to extract any citations made in that chunk of text.

- You will be given a list of extracted footnotes, a list of bibliography entries pre-extracted from the bibliography section of the full document and a chunk of text from that document.
- You need to return a list of citations made in that chunk of text.
- If there are no citations made in the chunk, return an empty list.
- The citation can be a footnote that can refer to multiple bibliography entries, so you need to return all the bibliography entries that the footnote refers to.
- If the chunk of text is a bibliographic entry itself, do not consider it a citation.
- If you're unable to match footnote indexes to the actual footnote content, either because the footnote is not in the list of footnotes or because no footnote content was provided, then you should use the bibliography entry index instead. For example, if [[10]](#fn10) has no footnote content you should use the bibliography entry of index 10 instead.

## Handling footnotes

Note that when you are given a footnote number, you need to look up the footnote in the list of footnotes, and then take the associated text for that footnote use that text to find the correct bibliography entry.

## Return format

For each citation, you need to return the following information:
- The text of the citation/footnote mark
- The type of the citation/footnote mark. This should be a value from the CitationType enum.
- The format of the citation/footnote mark, e.g., [number] or (Name, et al., Year), url, etc.
- A boolean value indicating whether the citation refers to a bibliography entry or footnote in the document so it expected to have an associated bibliography entry or footnote. For example, URLs often do not refer to a bibliography entry so this should be False, but something like (Doe, et al., 2025) does refer to a bibliography entry so this should be True.
- If the document includes a bibliography entry related to this citation, this will be an exact copy of that bibliography entry from the list of bibliography entries I'm providing separately, otherwise it will be an empty string. Do not include the entry number if there is one, just the full context of the bibliography entry.
- Your very brief rationale for why you think this is a citation/footnote mark.

## The list of footnotes extracted from the document

```
{footnotes_list}
```

## The list of bibliography entries (if any) extracted from the bibliography section of the full document

The indexes in this list should be used when returning index_of_associated_bibliography.

IMPORTANT: For numbered footnotes like [10], do NOT assume the number matches the list index. Instead, find the footnote definition in the full document (e.g., "10. ...") and match its content to the correct bibliography entry below.

```
{bibliography}
```

## The chunk of text to extract citations from

```
{chunk}
```
"""
)


class CitationDetectorAgent(LangChainAgent):
    name = "Citation Detector"
    description = "Detect citations in chunks with footnotes list"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = CitationResponse

    async def ainvoke(
        self, prompt_kwargs: dict, config: Optional[RunnableConfig] = None
    ) -> CitationResponse:
        messages = _citation_detector_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
