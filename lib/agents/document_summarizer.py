# %%
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.env import config
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class DocumentSummary(BaseModel):
    title: str = Field(
        description="The title of the document. Suggest a clear, concise title if the document does not have one."
    )
    authors: str = Field(
        description="The authors of the document (if available, otherwise empty string)."
    )
    publication_date: str = Field(
        description="The publication date of the document, or 'Unknown' if not available."
    )
    abstract: str = Field(
        description="The abstract of the document, or 'Unknown' if not available."
    )
    summary: str = Field(
        description=(
            "A ~1000-word miniature version of the document (roughly 900–1100 words) "
            "that focuses on the main argument of the work. It should read like a "
            "compressed research report: clearly stating the central question or problem, "
            "the main claim/argument, the essential methods or analytical framework, the "
            "critical results, and how these results support the argument, while omitting "
            "tangential or overly detailed implementation information."
        )
    )


class DocumentSummarizerResponse(BaseModel):
    summary: DocumentSummary = Field(
        description="The structured miniature summary of the document."
    )


_document_summarizer_agent_prompt = ChatPromptTemplate.from_template(
    """
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

"""
)


class DocumentSummarizerAgent(LangChainAgent):
    name = "Document Summarizer"
    description = "Read a document and produce a ~1000-word argument-focused miniature version plus basic metadata."
    model = gpt_5_mini_model
    temperature = 0.5
    output_schema = DocumentSummarizerResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> DocumentSummarizerResponse:
        messages = _document_summarizer_agent_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


# Test script - can be run directly or imported
if __name__ == "__main__":
    import asyncio
    import os
    import sys
    from pathlib import Path

    from lib.services.converters.base import convert_to_markdown

    # Set the file path here, or pass it as a command line argument
    FILE_PATH = "tests/data/RAND_RRA3307-1.pdf"  # e.g., "tests/data/sample_document.md"
    FILE_PATH = "tests/data/case_1/main_document.md"

    async def test_document_summarizer(file_path: str):
        """Test the document summarizer agent with a given file."""
        # Resolve the file path (handle relative paths from project root)
        if not os.path.isabs(file_path):
            # Assume relative to project root
            project_root = Path(__file__).parent.parent.parent
            file_path = str(project_root / file_path)

        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return

        print(f"Reading file: {file_path}")
        print("-" * 80)

        # Convert file to markdown
        markdown_content = await convert_to_markdown(file_path)

        print(f"Document length: {len(markdown_content)} characters")
        print("Running document summarizer agent...")
        print("-" * 80)

        # Run the agent
        from lib.services.file_artifacts_service.mock import MockFileArtifactsService

        document_summarizer_agent = DocumentSummarizerAgent(
            ContextSchema(
                openai_api_key=config.OPENAI_API_KEY,
                vector_store=None,
                file_artifacts_service=MockFileArtifactsService(),
            )
        )
        response = await document_summarizer_agent.ainvoke(
            {"document": markdown_content}
        )

        # Print the results
        summary = response.summary
        print("\n" + "=" * 80)
        print("DOCUMENT SUMMARY")
        print("=" * 80)
        print(f"\nTitle: {summary.title}")
        print(f"Authors: {summary.authors or 'N/A'}")
        print(f"Publication Date: {summary.publication_date}")
        print(f"\nAbstract:\n{summary.abstract}")
        print("\n" + "-" * 80)
        print("Summary (~1000 words):")
        print("-" * 80)
        print(summary.summary)
        print("\n" + "=" * 80)

    # Get file path from command line or use the FILE_PATH variable
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    elif FILE_PATH:
        file_path = FILE_PATH
    else:
        print("Usage: python document_summarizer_new.py <file_path>")
        print("   or: Set FILE_PATH variable in the script")
        sys.exit(1)

    # Run the test
    asyncio.run(test_document_summarizer(file_path))
