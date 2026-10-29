# %%
from typing import cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.workflows.document_summarization.state import DocumentSummary


class DocumentSummarizerResponse(BaseModel):
    summary: DocumentSummary = Field(
        description="The structured miniature summary of the document."
    )


_document_summarizer_agent_prompt = ChatPromptTemplate.from_template("""
# Task
You are an expert research analyst and document summarizer. You are given a document and must produce a ~1000-word miniature version of it that focuses on the main argument and its essential support.

The document may be long (e.g., 10,000+ words) and may NOT be cleanly structured into sections like "Abstract", "Introduction", etc. You must infer the structure and argument from the content itself.

## Your goals

1. Read the entire document holistically. Do not rely on section headers.
2. Identify:
   - The **core question or problem** the document addresses.
   - The **main argument or central claim** the document is making.
   - The **essential components** that support this argument, such as:
     - Key theoretical assumptions or frameworks
     - Core methodology or analytical approach
     - Experimental or simulation setup, if crucial
     - Pivotal empirical or computational results
     - The main reasoning steps linking results to the conclusion
3. Exclude:
   - Tangential details and side discussions
   - Long lists of secondary results
   - Implementation minutiae or technical background that do not materially affect the argument

## Output requirements

You must extract and return:

- The **title** of the document. If none is obvious, propose a clear, concise title.
- The **authors** (if available).
- The **publication date** (if available).
- The **abstract** (if available; otherwise return 'Unknown').
- Use at least fourth level headings (####) to structure the summary.
- A field called **summary** that is a **coherent, self-contained miniature version** of the document, approximately 900–1100 words, which:

  - States the central question or problem.
  - Presents the main argument or thesis.
  - Describes the essential methods or analytical framework (only as detailed as needed to understand the argument).
  - Summarizes the critical findings or results that support the argument.
  - Explains how these findings lead to the conclusions.
  - Articulates the overall significance or contribution of the work.

This summary should feel like a compressed research report focused on the argument and its reasoning chain, not just a list of bullet points and not a superficial high-level summary. Format it in paragraphs with markdown section titles including # styled headings.

## The document to analyze

{document}

""")


class DocumentSummarizerAgent(LangChainAgent):
    name = "Document Summarizer"
    description = "Read a document and produce a ~1000-word argument-focused miniature version plus basic metadata."
    model = gpt_5_6_terra_model
    output_schema = DocumentSummarizerResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig | None = None,
    ) -> DocumentSummarizerResponse:
        messages = _document_summarizer_agent_prompt.format_messages(**prompt_kwargs)
        return cast(
            DocumentSummarizerResponse,
            await self.llm.ainvoke(messages, config=config),
        )
