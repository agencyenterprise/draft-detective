"""LLM-based sentence tokenization for complex academic text."""

from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model

from lib.models.agent import DEFAULT_LLM_TIMEOUT
from lib.config.llm_models import gpt_5_mini_model
from lib.services.fragment_detection import DetectionMethod
from lib.workflows.claim_substantiation.context import ContextSchema


# Default detection method for identifying when to use LLM fallback
FRAGMENT_DETECTION_METHOD: DetectionMethod = "reconstruction"


class SentenceChunks(BaseModel):
    """Response model for LLM-based sentence tokenization."""

    chunks: List[str] = Field(
        description="List of sentence-level chunks. Citations should be kept as single chunks."
    )


async def llm_tokenize_paragraph(paragraph: str, context: ContextSchema) -> List[str]:
    """
    Use LLM to intelligently tokenize a paragraph into sentences.
    Handles complex cases like citations that NLTK struggles with.

    Args:
        paragraph: The text to tokenize

    Returns:
        List of sentence chunks

    Raises:
        Exception: If LLM API call fails (timeout, rate limit, etc.)
    """
    prompt = ChatPromptTemplate.from_template(
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

    llm = init_chat_model(
        gpt_5_mini_model.model_name,
        temperature=0,
        timeout=DEFAULT_LLM_TIMEOUT,
        api_key=context.openai_api_key,
    ).with_structured_output(SentenceChunks)

    try:
        messages = prompt.format_messages(paragraph=paragraph)
        result = await llm.ainvoke(messages)
        return result.chunks
    except Exception as e:
        raise Exception(f"LLM tokenization failed for paragraph: {e}") from e
