from __future__ import annotations

from enum import Enum

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_model
from lib.models.agent import LangChainAgent


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
        description="A single sentence summary of what the authors should update in the report"
    )
    date_generated: str = Field(
        description="The date the report was generated in YYYY-MM-DD format"
    )


class ReportOutput(BaseModel):
    report_markdown: str = Field(description="The markdown formatted report")
    report_metadata: ReportMetadata


_addendum_prompt = ChatPromptTemplate.from_template(
    """
You are a professional technical writer. Your job is to turn raw model output into a clear, concise, and action-oriented **claim update report** based on the structure used in “Live Reports: Addendum.”

Your report must:
- Focus on the most important updates.
- Clearly explain what the authors need to change.
- Use simple language and avoid dense technical jargon.

---

# How to Select the Most Important Updates
Choose only the updates that matter most for the main argument of the report. Use the document summary for guidance.
Rules:
- Include only the claims that meaningfully shift the report’s reasoning or conclusions.
- Keep the total number of references under 10.
- Include URLs whenever possible.

---

# Required Report Structure

Format your final response in **Markdown** using the following sections, in this exact order:

# Addendum: [Report Title or Topic]

### High Level Summary
Write a short (3-5 sentence) overview that answers these questions:
- What do the authors need to change in their report? Be specific about which sections or claims need updating.
- How should they change it? Tell them the direction: should they strengthen their conclusions, soften them, reverse them completely, or add more nuance?
- Why does this matter? Explain what happens if they don't make these changes - what are the consequences?

Think of this like a quick briefing. Someone should be able to read just this section and understand what needs to happen. Use everyday words, not academic jargon.

Example good opening: "Recent studies published in 2024 contradict the main finding in Section 3. The authors should revise their conclusion about X to reflect that Y is now the dominant view. If they don't update this, readers may lose trust in the report's accuracy."

### Background Updates
This section is for fixing the foundation of the report - the context and background information that supports the claims.

For each update, do this:
- Start with a clear statement about what's new. Use phrases like "New evidence shows...", "Recent data indicates...", or "A 2024 study found...". This grabs attention immediately. When referencing a specific source, use an inline markdown link: `[Smith et al. (2024)](https://example.com/study)`.
- Then tell them exactly what to change. Don't just say "update the background" - say "Add a paragraph explaining that Method X has been replaced by Method Y in recent research (see [Johnson (2023)](https://example.com/research))" or "Remove the claim about Z being rare, since [2023 data](https://example.com/data) shows it's now common."
- Explain why this change matters. Connect it back to the main argument - how does this background change affect what the report is trying to prove?

Keep each item short (1-3 sentences). If you have multiple background updates, use bullets. Make sure each one is actionable - the authors should know exactly what to do. Always include URLs as inline markdown links when available.

### Methodology Updates
This is where you tell them how to fix their research methods, procedures, or ways of analyzing data.

Be specific about:
- What method needs changing? Is it the way they collected data, the way they analyzed it, or the tools they used?
- How should they change it? Give them concrete steps. For example: "Replace the 2020 survey methodology with the updated 2024 version that includes online responses" or "Add a sensitivity analysis using the approach described in [Smith et al. (2024)](https://example.com/paper)."
- When should they cite sources? If there's a specific paper or standard they should reference, include it as an inline markdown link. Use the format `[Author(s) (Year)](URL)` or `[Ref 1](URL)` when referencing. For example: "see [Johnson (2024)](https://example.com/protocol) for the updated protocol" or "follow the guidelines in [Ref 2](https://example.com/guidelines)."

Don't just say "update the methodology" - tell them what part of the methodology and what to do about it. Think about what a researcher would need to know to actually make this change.

### Results Updates
Here you explain how the new information changes what the report found or how to interpret those findings.

For each result that needs updating:
- State what the original result was (briefly) and how new information changes it. For example: "The report states that X increased by 5%. New data shows it actually increased by 8%, so update the figure and the discussion."
- Explain what this means for the report's conclusions. Does this make the conclusions stronger? Weaker? Do they need to be completely rewritten?
- If there are numbers or statistics that changed, be clear about the old value and the new value. Don't make the authors guess.

Remember: results updates aren't just about numbers. Sometimes new information changes how you should interpret the same numbers. Explain that too.

### Implications Updates
This is the "so what?" section. You've told them what to change in the background, methods, and results. Now explain what all of this means for the big picture.

For each implication:
- Start with a clear statement about what needs to happen. Use direct language like "This requires the authors to..." or "This suggests they should..." or "The report must now acknowledge that..."
- Connect the dots. Show how the background changes, method changes, and result changes all work together to affect the main conclusions.
- Be prescriptive but fair. Tell them what they need to do, but explain why. For example: "This requires adding a section discussing the limitations of the original methodology, because readers need to understand why the updated approach is more reliable."

Think about what someone reading the updated report would need to understand. What questions would they have? Answer those questions here.

### References
Format references as numbered list items with inline markdown links:
1. [Author(s)]. (Year). *Title*. [Source or journal]. [Link](URL)
2. [Author(s)]. (Year). *Title*. [Source or journal]. [Link](URL)

If a URL is available in the input data, always include it as a markdown link. The link text can be "Link", "DOI", or the URL itself.

# Additional Requirements
1. Use simple language and clear causal phrasing
2. Keep each update to **1-3 sentences**.
3. **Use inline markdown links for citations within the text**. When mentioning a reference, format it as `[Author(s) (Year)](URL)` or `[Ref N](URL)` where N is the reference number. Always include the URL if it's available in the input data.
4. In the References section, format each reference with an inline markdown link at the end: `[Link](URL)` or `[DOI](URL)`.
5. Output **only Markdown**—no commentary or explanation.

---

# Categorize the Updates

At the end of your JSON output, categorize the update using one of:

- **No Update Needed**
  - **Description:** The original statements remain accurate and relevant.
  - **Use When:** The latest data or findings confirm the report's original conclusions.
  - **Example:** *Economic forecasts for Q1 remain consistent with initial estimates.*

---

- **Minor Factual Update**
  - **Description:** The authors should make small factual changes that slightly adjust quantitative or descriptive details.
  - **Use When:** Numbers, dates, or labels have shifted but the interpretation stays the same.
  - **Example:** *Inflation rate updated from 3.1% to 3.3%.*

---

- **Moderate Update (Clarification or Expansion)**
  - **Description:** The authors should introduce new context, explanation, but the overall conclusions still hold.
  - **Use When:** Recent data adds nuance, or terminology has evolved.
  - **Example:** *Add note on revised methodology in 2025 dataset.*

---

- **Major Update Required**
  - **Description:** The authors need to make substantive changes to sections or conclusions are needed due to new evidence.
  - **Use When:** New findings contradict or significantly extend prior statements.
  - **Example:** *2025 emissions data show a reversal of the downward trend reported in 2023.*

---

- **Outdated or Invalidated**
  - **Description:** The important claims and argument in the report are no longer accurate or applicable due to major developments.
  - **Use When:** The core premise or supporting data has been superseded.
  - **Example:** *Earlier projections invalidated by new regulatory changes in 2024.*

Choose the one that best matches the scale of the recommended changes.

---

# Additional Metadata to Include in JSON Output
- **title:** A short newspaper-style headline summarizing the addendum.
- **sentence_summary:** One-sentence overview of what the authors should update in the report. Include links to the important sources that support the update.
- **date_generated:** Current date in YYYY-MM-DD.

---

#### Input Data:
Live Reports Analysis
```
{records_json}
```

{domain_context}

{audience_context}

## Title: {document_title}
## Summary (optional): {document_summary}

#### Output:
Return one JSON object matching the required schema exactly.
"""
)


class AddendumReportGeneratorAgent(LangChainAgent):
    name = "Addendum Report Generator"
    description = (
        "Aggregate live reports and produce a markdown formatted addendum report"
    )
    model = gpt_5_model
    temperature = 0.2
    output_schema = ReportOutput

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> ReportOutput:
        messages = _addendum_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
