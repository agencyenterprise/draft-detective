from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.literature_review import ReferenceType
from lib.agents.methodology_extractor import ReproducibilityCategoryResponse
from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class SummaryAndOutput(BaseModel):
    summary: str = Field(
        description="A one to two sentence summary of the related section."
    )
    markdown_output: str = Field(
        description="Markdown formatted output of the full context of the related section."
    )


class ReferenceMinimal(BaseModel):
    title: str = Field(
        description="Canonical title for the reference exactly as it should appear in the article's bibliography"
    )
    type: ReferenceType = Field(
        description=f"Format classification for the reference. Possible values: {[e.value for e in ReferenceType]}"
    )
    link: str = Field(
        description="Stable URL or DOI that lets the author retrieve the reference quickly"
    )
    bibliography_info: str = Field(
        description="Bibliography entry formatted in the article's style; reuse the existing entry when the source is already in the bibliography"
    )


class MethodologyComparisonResponse(BaseModel):
    reproducibility: ReproducibilityCategoryResponse = Field(
        description="The class of reproducibility of the methodology."
    )
    extracted_methodology: SummaryAndOutput = Field(
        description="The extracted methodology of the paper."
    )
    field_methods_overview: SummaryAndOutput = Field(
        description="The overview of the field methods."
    )
    alignment_with_field_practice: SummaryAndOutput = Field(
        description="The alignment of the paper's methodology with the field methods."
    )
    methodological_rigor_and_risks: SummaryAndOutput = Field(
        description="The rigor and risks of the paper's methodology."
    )
    suggestions_for_improvements: SummaryAndOutput = Field(
        description="The suggestions for improvements to the paper's methodology."
    )
    references: List[ReferenceMinimal] = Field(
        default=[], description="List of sources cited from web search"
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

{extracted_methodology}

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

For the markdown output of the sections, you must:
- Approximately **500–900 words** for the overview, alignment, and rigor and risks sections.
- Approximately **200–400 words** for the suggestions for improvements section.
- Structured using markdown formatting as shown in the template below.
- **Mathematical notation**: Any equations, formulas, or mathematical expressions must be written in LaTeX format using `$...$` for inline math and `$$...$$` for display equations.

### Suggested Markdown Format

Format your response using the following markdown structure:

```markdown
## Extracted Methodology

[Include the full extracted methodology from the paper here. This should be a complete restatement or copy of the methodology provided in the input. Present it clearly and comprehensively so readers understand exactly what methodology was used in the paper before seeing the comparison.]

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
- Always use proper LaTeX syntax for mathematical notation (e.g., `\\alpha`, `\\beta`, `\\sum`, `\\prod`, `\\frac{{a}}{{b}}`, `\\sqrt{{x}}`, etc.)
- When describing equations from the paper, convert them to LaTeX format rather than using plain text or Unicode characters

Additional guidance:

- **Start with the extracted methodology**: The first section must be "## Extracted Methodology" and should contain the full methodology from the paper. This allows readers to understand what was done before seeing how it compares to the field.
- **CRITICAL**: You MUST include citations for all claims about field practices that come from web search.
- Format citations as markdown links: [Source Title](URL) immediately after the claim.
- Base your reasoning on the provided paper methodology and information found through web search.
- When something seems important but is not specified in the paper methodology, explicitly note that it is **not specified** rather than guessing.
- You may generalize about the field when it is clearly supported by web search results, but avoid fabricating very specific claims or citations.
- When using web search results, cite the sources appropriately in your comparison narrative.

# NOTE:
When generating responses,REMOVE OR REPLACE ALL INTERNAL CITATION TOKENS SUCH AS turn1search0, turn2search3, or similar. DO NOT DISPLAY RAW REFERENCE IDS OR METADATA MARKERS IN THE FINAL TEXT. RETURN CLEAN, HUMAN-READABLE OUTPUT ONLY.

Now write the comparison as described above.
"""
)


class MethodologyComparisonAgent(LangChainAgent):
    name = "Methodology Comparison Agent"
    description = (
        "Compare an extracted paper methodology to typical methods used in the broader field, "
        "using web search to find field methods context, and return a structured text comparison."
    )
    model = gpt_5_2_model
    temperature = 0.3
    timeout = 600
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> MethodologyComparisonResponse:
        """
        Expected prompt_kwargs:
            {
                "extracted_methodology": str,  # output of MethodologyExtractorAgent
            }
        """
        prompt = _methodology_comparison_agent_prompt.invoke(prompt_kwargs)

        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=MethodologyComparisonResponse,
        )

        result = await agent.ainvoke(  # type: ignore[call-overload]
            {"messages": [HumanMessage(content=prompt.to_string())]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
