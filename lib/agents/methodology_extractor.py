# %%
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.env import config
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.claim_substantiation.context import ContextSchema


class MethodologyExtractionResponse(BaseModel):
    methodology: str = Field(
        description=(
            "A concise but detailed and reproducible description of the methodology used in the document "
            "to obtain its results. This should be comprehensive enough that a technically "
            "literate researcher could reproduce the work. Include step-by-step procedures, "
            "exact parameters, software versions, data preprocessing details, and all "
            "implementation choices that materially affect results. Focus on procedures, "
            "data, models, experimental setups, and analysis workflows, avoiding background "
            "or interpretation."
        )
    )


_methodology_extractor_agent_prompt = ChatPromptTemplate.from_template(
    """
# Task
You are an expert scientific reader and methodology analyst. You are given a research document (or a long excerpt of one) and must extract ONLY the methodology used to obtain the results.

The document may be long (e.g., 10,000+ words) and may NOT be cleanly structured into sections like "Methods" or "Methodology". You must infer the methodological content from the text itself.

## Your goals

1. Read the document holistically. Do not rely solely on section headers.
2. Identify and describe the **procedures and processes** used to obtain the results in sufficient detail for reproduction, including as relevant:
   - Data sources, datasets, and sampling strategy (with specific details about data collection, selection criteria, sample sizes)
   - Experimental or observational setup (equipment specifications, conditions, interventions, groups, control variables)
   - Computational or analytical methods (algorithms, models, estimators, simulations with specific parameters)
   - Training, fitting, or calibration procedures (learning rates, optimization algorithms, convergence criteria, number of epochs/iterations)
   - Evaluation or validation procedures (metrics with exact definitions, baselines, statistical tests with significance levels)
   - Software versions, library versions, and tool specifications when mentioned
   - Randomization seeds, initialization procedures, and any stochastic elements
   - Data preprocessing steps in detail (normalization, filtering, transformation procedures)
   - Any key implementation choices that materially affect the results
3. Exclude:
   - High-level motivation and background theory that do not directly describe what was done
   - Extended literature review or related work
   - Interpretations of results, discussion, implications, or conclusions

## Reproducibility Requirements

The methodology should be detailed enough that a technically literate researcher could reproduce the work. This means:

- **Step-by-step procedures**: Document the exact sequence of steps taken, in order
- **Specific values**: Include exact parameters, hyperparameters, and configurations when available
- **Software specifications**: Note software versions, library versions, and tool specifications when mentioned in the document
- **Data details**: Include specific information about data preprocessing, transformations, and handling
- **Implementation details**: Document any randomization seeds, initialization procedures, or stochastic elements
- **Evaluation specifics**: Include exact definitions of metrics, evaluation procedures, and statistical tests

You may use markdown formatting to structure the methodology (e.g., sections, lists) if it improves clarity and reproducibility.

## Output requirements

You must return a single field called **methodology** which is:

- A **coherent, stand-alone narrative** that is detailed enough for reproduction (approximately **500–1000 words**, or longer if needed for completeness).
- Written in clear prose that could be read by a technically literate researcher unfamiliar with the paper.
- Focused on **what was actually done** to generate the results, with sufficient detail to enable reproduction.
- Structured clearly, potentially using markdown formatting (sections, lists) to organize complex procedures.
- Emphasizes completeness and reproducibility over conciseness.

When important details are truly missing from the provided text (e.g., sample size, exact hyperparameters, full experimental conditions, software versions), explicitly indicate this with phrases like:
- "The exact sample size is not specified in the provided text."
- "Details of the optimization procedure are not specified in the provided text."
- "The software version used is not specified in the provided text."

Do **not** invent or guess specific values or procedures that are not clearly supported by the document.

## The document to analyze

{document}
"""
)


class MethodologyExtractorAgent(LangChainAgent):
    name = "Methodology Extractor"
    description = (
        "Read a research document and extract a detailed, reproducible description of "
        "the methodology used to obtain the results, with sufficient detail for external "
        "researchers to reproduce the work."
    )
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = MethodologyExtractionResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> MethodologyExtractionResponse:
        messages = _methodology_extractor_agent_prompt.format_messages(**prompt_kwargs)
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
    # FILE_PATH = "tests/data/case_1/main_document.md"
    FILE_PATH = "rand-personal/sample_papers_rand/RAND_RRA3034-1.pdf"

    async def test_methodology_extractor(file_path: str):
        """Test the methodology extractor agent with a given file."""
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
        print("Running methodology extractor agent...")
        print("-" * 80)

        # Run the agent
        methodology_extractor_agent = MethodologyExtractorAgent(
            ContextSchema(openai_api_key=config.OPENAI_API_KEY, vector_store=None)
        )
        response = await methodology_extractor_agent.ainvoke(
            {"document": markdown_content}
        )

        # Print the results
        print("\n" + "=" * 80)
        print("METHODOLOGY EXTRACTION")
        print("=" * 80)
        print(response.methodology)
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
    asyncio.run(test_methodology_extractor(file_path))
