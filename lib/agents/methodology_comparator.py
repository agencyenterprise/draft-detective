# %%
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.env import config
from lib.config.llm_models import gpt_5_model
from lib.models.agent import DirectOpenAIAgent
from lib.services.openai import (
    ensure_structured_output_response,
    wait_for_response,
)
from lib.workflows.claim_substantiation.context import ContextSchema


class MethodologyComparisonResponse(BaseModel):
    comparison: str = Field(
        description=(
            "A structured, text-based comparison between the paper's methodology and "
            "typical methods in the broader field, based on web search findings."
        )
    )


_methodology_comparison_agent_prompt = PromptTemplate.from_template(
    """
# Task
You are an expert methodological reviewer in the relevant scientific field. You are given:

1. A description of a **paper's methodology** (what this paper actually did to obtain its results).

Your job is to compare the paper's methodology to the broader field's methods and produce a clear, structured narrative. You must use web search to find information about typical methods used in the broader field.

## Web Search Instructions

Use web search to:
- Find typical or canonical methods used in the broader field for similar problems
- Identify standard practices, data sources, experimental setups, and analytical techniques
- Locate authoritative sources (peer-reviewed articles, methodological reviews, field standards)
- Gather information about evaluation practices and rigor standards in the field

When using web search:
- Focus on high-quality sources (peer-reviewed publications, methodological reviews, field standards)
- Search for terms related to the paper's methodology and the broader field
- Look for systematic reviews, meta-analyses, or methodological guidelines when available
- Consider different disciplinary perspectives if relevant

## Inputs

### Paper methodology

This is the methodology as extracted from the focal paper:

{paper_methodology}

## Your goals

1. **Characterize the field baseline.**
   - Use web search to identify and briefly restate what appears to be *standard practice* in the field.
   - Focus on typical data sources, experimental/observational setups, modeling or analytical techniques, and evaluation practices.

2. **Compare the focal paper to the field baseline.**
   - Identify key **similarities** between the paper's methodology and standard field practice.
   - Identify key **differences** or **innovations** in the paper's methodology.
   - Identify any **missing standard components** (things that are common in the field but absent or very weak in the paper).
   - Comment on the **rigor and robustness** of the paper's methodology relative to the field norm (e.g., more rigorous, similar, weaker).

3. **Highlight implications and risks.**
   - Explain how the similarities and differences might affect the **credibility**, **generalizability**, or **interpretability** of the paper's results.
   - Point out any methodological **risks or limitations** that follow from the paper's deviations from standard practice, or from omissions of common checks.

## Output requirements

You must return a single field called **comparison** which is:

- A **coherent, stand-alone narrative** written in clear prose.
- Approximately **500–900 words** for the comparison sections (the extracted methodology section adds additional length).
- Structured using markdown formatting as shown in the template below.
- **Mathematical notation**: Any equations, formulas, or mathematical expressions must be written in LaTeX format using `$...$` for inline math and `$$...$$` for display equations.

### Suggested Markdown Format

Format your response using the following markdown structure:

```markdown
## Extracted Methodology

[Include the full extracted methodology from the paper here. This should be a complete restatement or copy of the methodology provided in the input. Present it clearly and comprehensively so readers understand exactly what methodology was used in the paper before seeing the comparison.]

Organize the methodology using the following subsections as appropriate (use only those that are relevant to the paper):

### Research Design

[Describe the overall research design, study type (e.g., experimental, observational, simulation, meta-analysis), and the general approach taken.]

### Data Sources and Collection

[Describe the data sources used, how data was collected, sampling methods, data acquisition procedures, and any data preprocessing steps.]

### Experimental Setup

[For experimental studies: describe the experimental conditions, controls, variables manipulated, and experimental procedures. For observational studies: describe the observational framework, measurement instruments, and data collection protocols.]

### Analytical Methods

[Describe the statistical methods, modeling approaches, algorithms, computational techniques, or other analytical methods used to analyze the data or test hypotheses.]

### Evaluation Metrics and Validation

[Describe how results were evaluated, what metrics were used, validation procedures, robustness checks, and any quality assurance measures.]

### Limitations and Constraints

[Note any limitations, constraints, or assumptions explicitly mentioned in the methodology, including sample size limitations, data quality issues, or methodological constraints.]

**Note:** If the extracted methodology does not clearly separate into these categories, present it in a logical flow that best represents the paper's methodological approach. The goal is clarity and comprehensiveness, not rigid adherence to this structure.

## Field Methods Overview

[Brief overview of standard practices in the field, based on web search findings. Describe typical data sources, experimental setups, analytical techniques, and evaluation practices used in the broader field.]

## Alignment with Field Practice

### Similarities

[Identify and describe key similarities between the paper's methodology and standard field practice. Use bullet points or paragraphs as appropriate.]

### Differences and Innovations

[Identify and describe key differences or innovations in the paper's methodology compared to standard practice. Highlight what makes the approach novel or different.]

### Missing or Weak Standard Components

[Identify any standard components that are common in the field but absent or weak in the paper. Explain what is typically expected and what is missing.]

## Methodological Rigor and Risks

[Assess the rigor and robustness of the paper's methodology relative to field norms. Explain implications for credibility, generalizability, and interpretability. Highlight any methodological risks or limitations that follow from deviations from standard practice.]

## Suggestions for Improvements

[Based on previous analyses provide a bulleted list of at most three suggestions to change the language of the paper, the data sources used, methodological approaches, etc. to improve the robustness, rigor, or generalizability of the findings.]


### Citations

[When referencing sources found through web search, cite them appropriately using markdown links or inline citations, for example: "According to [Source Name](URL)..." or "Smith et al. (2023) found that..."]
```

**Formatting Guidelines:**
- Use `##` for main sections (level 2 headings)
- Use `###` for subsections (level 3 headings)
- Use `**bold**` for emphasis on key terms
- Use bullet points (`-`) or numbered lists when listing multiple items
- Use code blocks (`` ` ``) for technical terms or specific values
- Include citations with markdown links when referencing web search sources
- Keep paragraphs focused and well-structured
- **Mathematical equations**: All equations must be formatted in LaTeX notation:
- For inline equations, use single dollar signs: `$E = mc^2$`
- For block/display equations, use double dollar signs on separate lines:
```latex
$$E = mc^2$$
```
- Always use proper LaTeX syntax for mathematical notation (e.g., `\alpha`, `\beta`, `\sum`, `\prod`, `\frac{a}{b}`, `\sqrt{x}`, etc.)
- When describing equations from the paper, convert them to LaTeX format rather than using plain text or Unicode characters

Additional guidance:

- **Start with the extracted methodology**: The first section must be "## Extracted Methodology" and should contain the full methodology from the paper. This allows readers to understand what was done before seeing how it compares to the field.
- Base your reasoning on the provided paper methodology and information found through web search.
- When something seems important but is not specified in the paper methodology, explicitly note that it is **not specified** rather than guessing.
- You may generalize about the field when it is clearly supported by web search results, but avoid fabricating very specific claims or citations.
- When using web search results, cite the sources appropriately in your comparison narrative.

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

Now write the comparison as described above.
"""
)


class MethodologyComparisonAgent(DirectOpenAIAgent):
    name = "Methodology Comparison Agent"
    description = (
        "Compare an extracted paper methodology to typical methods used in the broader field, "
        "using web search to find field methods context, and return a structured text comparison."
    )
    model = gpt_5_model
    temperature = 0.3
    output_schema = MethodologyComparisonResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> MethodologyComparisonResponse:
        """
        Expected prompt_kwargs:
            {
                "paper_methodology": str,  # output of MethodologyExtractorAgent
            }
        """
        prompt = _methodology_comparison_agent_prompt.invoke(prompt_kwargs)
        input = [{"role": "user", "content": prompt.text}]

        response = await self.client.responses.parse(
            model=self.model.name,
            tools=[{"type": "web_search"}],
            max_tool_calls=20,
            reasoning={
                "effort": "low",  # "minimal", "low", "medium", "high"
                "summary": "auto",
            },
            text_format=MethodologyComparisonResponse,
            background=True,
            input=input,
        )

        response = await wait_for_response(
            self.client, response, log_info="Methodology Comparison Agent"
        )
        return ensure_structured_output_response(
            response, MethodologyComparisonResponse
        )


# Test script - can be run directly or imported
if __name__ == "__main__":
    import asyncio
    import os
    import sys
    from pathlib import Path

    from lib.agents.methodology_extractor import MethodologyExtractorAgent
    from lib.services.converters.base import convert_to_markdown

    async def test_methodology_comparison(
        file_path: str,
    ):
        """Test the methodology comparison agent with a given file.

        This function:
        1. Converts the file to markdown
        2. Extracts the methodology using MethodologyExtractorAgent
        3. Compares the methodology to field standards using MethodologyComparisonAgent
        """
        # Resolve file path (handle relative paths from project root)
        if not os.path.isabs(file_path):
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
        print("-" * 80)

        # Initialize context
        context = ContextSchema(openai_api_key=config.OPENAI_API_KEY, vector_store=None)

        # Step 1: Extract methodology
        print("Step 1: Extracting methodology from document...")
        print("-" * 80)
        methodology_extractor_agent = MethodologyExtractorAgent(context)
        extraction_response = await methodology_extractor_agent.ainvoke(
            {"document": markdown_content}
        )

        paper_methodology = extraction_response.methodology
        print(f"Extracted methodology length: {len(paper_methodology)} characters")
        print("\n" + "=" * 80)
        print("EXTRACTED METHODOLOGY")
        print("=" * 80)
        print(paper_methodology)
        print("\n" + "=" * 80)

        # Step 2: Compare methodology to field standards
        print("Step 2: Comparing methodology to field standards using web search...")
        print("-" * 80)
        methodology_comparison_agent = MethodologyComparisonAgent(context)
        comparison_response = await methodology_comparison_agent.ainvoke(
            {
                "paper_methodology": paper_methodology,
            }
        )

        # Print the results
        print("\n" + "=" * 80)
        print("METHODOLOGY COMPARISON")
        print("=" * 80)
        print(comparison_response.comparison)
        print("\n" + "=" * 80)

    # Default file path (adjust to your repo layout)
    DEFAULT_FILE_PATH = "rand-personal/sample_papers_rand/RAND_RRA3034-1.pdf"

    # Get file path from command line or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = DEFAULT_FILE_PATH

    # Run the test
    asyncio.run(test_methodology_comparison(file_path))
