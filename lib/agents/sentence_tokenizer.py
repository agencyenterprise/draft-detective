"""LLM-based sentence tokenization for complex academic text."""

from typing import List, Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class SentenceChunks(BaseModel):
    """Response model for LLM-based sentence tokenization."""

    chunks: List[str] = Field(
        description="List of sentence-level chunks. Citations should be kept as single chunks."
    )


_sentence_tokenizer_prompt = ChatPromptTemplate.from_template(
    """You are a sentence tokenization expert for academic documents.

Your task: Split the given text into sentence-level chunks.

IMPORTANT RULES:
1. Academic citations should be kept as SINGLE chunks
   - Example: "Smith, J., & Doe, A. (2020). Title of Paper. Journal Name, 5(2), 123-145." → ONE chunk

2. Regular prose should be split at sentence boundaries (., ?, !)
   - Example: "This is sentence one. This is sentence two." → TWO chunks

3. Markdown citation references (e.g., [[1]](#footnote-0)) MUST stay with the preceding text
   - Example: "See the report.[[1]](#footnote-0)" → ONE chunk: "See the report.[[1]](#footnote-0)"
   - Example: "Results show 20% increase. [[25]](#footnote-24)" → ONE chunk: "Results show 20% increase. [[25]](#footnote-24)"
   - Footnotes always appear at the END of sentences, never at the beginning

4. PRESERVE all markdown formatting including:
   - List markers: *, -, 1., 2., etc.
   - Example: "* This is a list item.[[1]](#footnote-0)" → KEEP the "*" marker

5. Do NOT split at:
   - Author initials: "Smith, J."
   - Journal abbreviations: "Proc. Natl. Acad. Sci."
   - "et al."
   - URLs or DOIs containing periods
   - Before markdown citation references: [[digit]](#footnote-digit)

6. Each chunk should be a complete, meaningful unit of text

Text to tokenize:
```
{paragraph}
```"""
)


class SentenceTokenizerAgent(LangChainAgent):
    name = "Sentence Tokenizer"
    description = "Tokenize academic text into sentence-level chunks using LLM"
    model = gpt_5_mini_model
    temperature = 0
    output_schema = SentenceChunks

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> SentenceChunks:
        messages = _sentence_tokenizer_prompt.format_messages(**prompt_kwargs)
        return cast(
            SentenceChunks,
            await self.llm.ainvoke(messages, config=config),
        )
