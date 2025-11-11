from __future__ import annotations

from enum import Enum
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_model
from lib.models.agent import DEFAULT_LLM_TIMEOUT, AgentProtocol
from pydantic import BaseModel, Field


class UpdateType(str, Enum):
    """Defines the classification and metadata for a report update."""

    NO_UPDATE_NEEDED = "no_update_needed"
    MINOR_FACTUAL_UPDATE = "minor_factual_update"
    MODERATE_UPDATE = "moderate_update"
    MAJOR_UPDATE_REQUIRED = "major_update_required"
    OUTDATED_OR_INVALIDATED = "outdated_or_invalidated"


class ReportMetadata(BaseModel):
    update_type: UpdateType = Field(description="The type of update")
    title: str = Field(
        description="Newspaper-style title summarizing the changes (or lack of changes) suggested by the report"
    )
    sentence_summary: str = Field(
        description="A single sentence summary of the addendum report"
    )
    date_generated: str = Field(
        description="The date the report was generated in YYYY-MM-DD format"
    )


class ReportOutput(BaseModel):
    report_markdown: str = Field(description="The markdown formatted report")
    report_metadata: ReportMetadata


_addendum_prompt = ChatPromptTemplate.from_template(
    """
You are a professional technical writer formatting claim update reports based on the “Live Reports: Addendum” document style.

Your task is to **select the most salient updates and rewrite and format the raw model output** into a polished, Markdown-formatted report that mirrors the tone, structure, and logic of that template.

## Guidelines for Selecting the Most Salient Updates
- Select the updates that are most central to the argument of the report. (Use summary from the document to help you determine the most salient updates.) For example, if a claim is not associated with the central argument of the document, then updates for that claim should not be included in the report if other claims take precedence. 
- Limit the number of references to 10
- When possible provide url for the reference in the report.


---

## Structure or Report

#### Markdown Body

Given the raw model output below, rewrite and structure it into a **Markdown report** that mirrors the tone and layout of the following template.

---- template ----
```markdown
# Addendum: [Title of Report or Claim Update Topic]

## High Level Summary
- Provide a concise paragraph (3–5 sentences) summarizing the key updates, overall direction, or major implications.

## Background Updates
- Describe contextual or theoretical changes that influenced the claims.
- Each paragraph or bullet should start with a strong declarative phrase (e.g., “New analysis indicates…”).

## Methodology Updates
- Describe procedural, experimental, or analytical revisions.
- Keep items 1–3 sentences each.
- Reference supporting materials where relevant (e.g., “see Appendix A”).

## Results Updates
- State outcomes, comparisons, or numerical adjustments.
- Clearly mention any revised values (e.g., “updated from 5.5% to 4.1%”).

## Implications Updates
- Explain practical or strategic consequences of the above updates on the conclusions of report
- Use prescriptive tone (“This requires…”, “This suggests…”).

## References
1. [Author(s)]. (Year). *Title*. [Source or journal].
2. ...
```

--------

#### Requirements:
1. Use **section headers** in this order:
   - `# Addendum: [Report Title or Topic]`
   - `## High Level Summary`
   - `## Background Updates`
   - `## Methodology Updates`
   - `## Results Updates`
   - `## Implications Updates`
   - `## References`

2. Maintain a **formal and evidence-driven tone**, with clear causal or comparative phrasing (e.g., “This adjustment necessitates…”, “This modification ensures…”).

3. Each update paragraph should:
   - Begin with a concrete noun or action (“New analysis shows…”, “The dataset was expanded…”).
   - Reference supporting context or implications.
   - Remain **1–3 sentences** long.

4. Insert **numerical or symbolic citations** in square brackets `[1]`, `[2]`, etc., to mimic reference numbering.

5. End with a numbered reference list in plain-text style, e.g.:

[1] Author(s). (Year). Title. Journal or Source. URL (if available).

6. Output only **Markdown-formatted text** (no extra commentary).


## Categorize the updates

Within the output data structure place the report into one of the following categories which best matches the changes (or lack of changes) suggested by the report.

#### 1. **No Update Needed**
- **Description:** The original statements remain accurate and relevant.
- **Use When:** The latest data or findings confirm the report's original conclusions.
- **Example:** *Economic forecasts for Q1 remain consistent with initial estimates.*

---

#### 2. **Minor Factual Update**
- **Description:** Small factual changes that slightly adjust quantitative or descriptive details.
- **Use When:** Numbers, dates, or labels have shifted but the interpretation stays the same.
- **Example:** *Inflation rate updated from 3.1% to 3.3%.*

---

#### 3. **Moderate Update (Clarification or Expansion)**
- **Description:** New context, explanation, or clarification needed, but overall conclusions still hold.
- **Use When:** Recent data adds nuance, or terminology has evolved.
- **Example:** *Add note on revised methodology in 2025 dataset.*

---

#### 4. **Major Update Required**
- **Description:** Substantive changes to sections or conclusions are needed due to new evidence.
- **Use When:** New findings contradict or significantly extend prior statements.
- **Example:** *2025 emissions data show a reversal of the downward trend reported in 2023.*

---

#### 5. **Outdated or Invalidated**
- **Description:** The statement is no longer accurate or applicable due to major developments.
- **Use When:** The core premise or supporting data has been superseded.
- **Example:** *Earlier projections invalidated by new regulatory changes in 2024.*

### Additional Metadata

- title: Generate a Newspaper-style title summarizing the changes (or lack of changes) suggested by the report. This title should give the user a quick overview of the report.
- sentence_summary: Generate a single sentence summary of the addendum report. This summary should give the user a quick overview of the report.
- date_generated: The date the report was generated in YYYY-MM-DD format.


#### Input:
```
{records_json}
```

#### Additional context:
Document context: {domain_context}
Audience Context: {audience_context}
Title: {document_title}
Summary (optional): {document_summary}

#### Output:
Return one JSON object matching the required schema exactly.
    """
)


class AddendumReportGeneratorAgent(AgentProtocol):
    name: str = "Addendum Report Generator"
    description: str = (
        "Aggregate live reports and produce a markdown formatted addendum report"
    )

    def __init__(self):
        self.llm = init_chat_model(
            gpt_5_model.model_name, temperature=0.2, timeout=DEFAULT_LLM_TIMEOUT
        ).with_structured_output(ReportOutput)

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> ReportOutput:
        messages = _addendum_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


addendum_report_generator_agent = AddendumReportGeneratorAgent()
