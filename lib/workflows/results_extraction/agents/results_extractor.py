# %%
from enum import Enum

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.env import config
from lib.config.llm_models import gpt_5_mini_model
from typing import List, Optional, cast

from lib.agents.models import ReproducibilityCategory
from lib.models.agent import LangChainAgent
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.context import ContextSchema


class ResultType(Enum):
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    TEXT = "text"
    ALGORITHM = "algorithm"
    OTHER = "other"


class ResultSection(BaseModel):

    title: str = Field(
        description="A chosen title for the section. Can be extracted from the text if it is present, but it should be no more than five words."
    )
    description: str = Field(description="The description of the result section.")
    result_type: ResultType = Field(description="The type of the result section.")
    location: str = Field(
        description="Description of the location of the result section in the document. This should be a description of the page number, figure number, table number, equation number, etc."
    )
    reproducibility: ReproducibilityCategory = Field(
        description="The class of reproducibility of the result section."
    )
    reproducibility_rationale: str = Field(
        description="The rationale for why you think the result section is reproducible or not. Describe what is needed to make this particular section reproducible."
    )


class ResultsListResponse(BaseModel):
    result_sections: List[ResultSection] = Field(
        description="The list of result sections."
    )


_results_extractor_agent_prompt = ChatPromptTemplate.from_template(
    """
# Task
You are an expert scientific reader and results analyst. You will be given a research document (or a long excerpt of one), and must extract the main results of the document AND determine whether these each of these main results is reproducible given the information provided in the paper.

"Results" are defined as any qualitative, mathematical, or quantitative end-points of an analysis. Things that aren't included in results are assumptions or initial conditions.

The document may be long (e.g., 10,000+ words) and may NOT be cleanly structured into sections labeled as "Results."

## Your goals

1. Read the document holistically. Do not rely solely on section headers.
2. Identify the main results of the paper. "Results" are defined as any qualitative, mathematical, or quantitative end-points of an analysis. Things that aren't included in results are assumptions or initial conditions.
3. Determine the "Result Type"
    - Figure: The result is a figure within the text
    - Table: The result is a table within the text
    - Equation: The result is a final equation
    - Text: The result is a section of text (e.g., numerical statements within text)
    - Algorithm: The result is an algorithm stated in pseudo-code in text
    - Other: The result doesn't fit in any of the given categories
4. Determine the reproducibility class of the result based on the following criteria:
   - If the result is fully reproducible, return the class value "fully_reproducible".
   - If the result is reproducible if an AI agent is given access to web search, return the class value "reproducible_with_web_search".
   - If the result is reproducible provided the user uploads data, return the class value "reproducible_with_external_uploads".
   - If the result is not reproducible, return the class value "not_reproducible".
   Provide a rationale for this categorization and explain what would be needed to make the result fully reproducible
5. Describe the result in no more than five sentences
6. Provide the location of the result.  This should be a description of the page number, figure number, table number, equation number, etc
7. Provide a descriptive title for the result


## Results extraction guidelines

Results are sometimes represented as equations, figures, tables, or specific numerical quantities stated within the text. In general, they are defined as the end-points of some quantitative or qualitative analysis. For the results extraction, we want to extract results and put them within the same section according to their natural grouping within the paper. For example, a table could countain dozens of values, but it should represent a single result. Similarly with figures. Each of these particular results should have a reproducibility category.

## Reproducibility Criteria

- Fully Reproducible (Definition): Methodologies where the logic is fully explained and the necessary data (parameters, equations, prompts, or rubrics) is provided directly within the text or appendices. A coding agent or researcher could replicate these results immediately without external data additions. These studies primarily consist of mathematical models, simulations, and algorithmic pipelines where the "data" consists of algebraic formulas or specific parameters explicitly recorded in the report.

- Reproducible with Web Search (Definition): Methodologies where the logic is fully explained but the necessary data (parameters, equations, prompts, or rubrics) is not provided directly within the text or appendices. However, the data can be easily retrieved with web search.

- Reproducible with External Uploads (Definition): Methodologies where the logic is fully explained but the necessary data (parameters, equations, prompts, or rubrics) is not provided directly within the text or appendices. However, the data consists of public laws, historical documents, or open public datasets that a researcher can easily retrieve with data additions. These studies are largely legal reviews, historical analyses, or quantitative models using large public datasets (like ISO interconnection queues).

- Not Reproducible (Definition): Methodologies where the logic is not fully explained and/or the necessary data (parameters, equations, prompts, or rubrics) or the data cannot be easily obtained. Methodologies that cannot be reproduced even with web search capabilities because they rely on confidential, proprietary, or paid-access data that is not released..

## Reproducibility Requirements

If the result is fully reproducible, it should be detailed enough that a technically literate researcher could reproduce the work. This means:

- **Step-by-step procedures**: Document the exact sequence of steps taken, in order
- **Specific values**: Include exact parameters, hyperparameters, and configurations when available
- **Software specifications**: Note software versions, library versions, and tool specifications when mentioned in the document
- **Data details**: Include specific information about data preprocessing, transformations, and handling
- **Implementation details**: Document any randomization seeds, initialization procedures, or stochastic elements
- **Evaluation specifics**: Include exact definitions of metrics, evaluation procedures, and statistical tests

When important details are truly missing from the provided text (e.g., sample size, exact hyperparameters, full experimental conditions, software versions), explicitly indicate this with phrases like:
- "The exact sample size is not specified in the provided text."
- "Details of the optimization procedure are not specified in the provided text."
- "The software version used is not specified in the provided text."

Do **not** invent or guess specific values or procedures that are not clearly supported by the document.

## The document to analyze

{document}
"""
)


class ResultsExtractorAgent(LangChainAgent):
    name = "Results Extractor"
    description = "Read a research document and extract a detailed list of the results"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = ResultsListResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ResultsListResponse:
        messages = _results_extractor_agent_prompt.format_messages(**prompt_kwargs)
        return cast(
            ResultsListResponse,
            await self.llm.ainvoke(messages, config=config),
        )


# Test script - can be run directly or imported
if __name__ == "__main__":
    import asyncio
    import os
    import sys
    from pathlib import Path

    from lib.services.converters.base import convert_to_markdown

    # Set the file path here, or pass it as a command line argument
    # FILE_PATH = "tests/data/RAND_RRA3307-1.pdf"  # e.g., "tests/data/sample_document.md"
    # FILE_PATH = "tests/data/case_1/main_document.md"
    # FILE_PATH = "rand-personal/sample_papers_rand/RAND_RRA3034-1.pdf"
    FILE_PATH = "rand-personal/smaldino_reproduction/Smaldino_McElreath_(2016).pdf"

    async def test_results_extractor(file_path: str):
        """Test the results extractor agent with a given file."""
        # Resolve the file path (handle relative paths from project root)
        if not os.path.isabs(file_path):
            # Assume relative to project root
            project_root = Path(__file__).parent.parent.parent.parent.parent
            file_path = str(project_root / file_path)

        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return

        print(f"Reading file: {file_path}")
        print("-" * 80)

        # Convert file to markdown
        markdown_content = await convert_to_markdown(file_path)

        print(f"Document length: {len(markdown_content)} characters")
        print("Running results extractor agent...")
        print("-" * 80)

        # Initialize context
        context = ContextSchema(
            openai_api_key=config.OPENAI_API_KEY,
            vector_store=None,
            project_id="dev",
            file_artifacts_service=MockFileArtifactsService(),
        )

        # Run the agent
        results_extractor_agent = ResultsExtractorAgent(context)
        response = await results_extractor_agent.ainvoke({"document": markdown_content})

        results_list = response.result_sections
        for result in results_list:

            # Print the methodology results
            print("\n" + "=" * 80)
            print("EXTRACTED RESULT")
            print("Title:", result.title)
            print("Type:", result.result_type)
            print("Location:", result.location)
            print("Description:", result.description)
            print("\n" + "-" * 80)

            # Print the reproducibility results
            print("REPRODUCIBILITY ASSESSMENT")
            print(f"Category: {result.reproducibility.value}")
            print(f"\nRationale:\n{result.reproducibility_rationale}")
            print("\n" + "=" * 80)

    # Get file path from command line or use the FILE_PATH variable
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    elif FILE_PATH:
        file_path = FILE_PATH
    else:
        print("Usage: python methodology_extractor_agent.py <file_path>")
        print("   or: Set FILE_PATH variable in the script")
        sys.exit(1)

    # Run the test
    asyncio.run(test_results_extractor(file_path))
