---
name: methodology-comparison
description: Use this skill to compare a paper's methodology against standard practice in its scientific field (methodological alignment) — using web search to characterize the field baseline, then assessing similarities, differences, missing components, rigor/risks, and improvements. Invoke when the user asks whether a document's methodology matches standard/typical methods in the field, or for a methodological-alignment review.
---

<!-- interactive-only:start -->
## Before you search — get the user's consent

This check sends parts of the user's document to an external web search provider. Do not run a search, fetch a URL, or call any other web tool until the user has explicitly agreed to it in this conversation.

1. If you do not already have the user's consent for this document in this conversation, relay this to them verbatim and stop for their answer:

   > To run this assessment, parts of your document — and possibly the whole document — will be sent to a web search provider as search queries. Don't proceed if the document contains confidential information you aren't comfortable sharing with an external search engine. Do you consent to running web search on this document?

2. Continue only on an explicit yes. One consent covers this document for the rest of the conversation — don't re-ask per reference or per section.
3. If the user declines, stop and do not search. Do not fall back on memory or on what you can infer without searching, and do not report partial findings as if the check ran. Say the check needs web access, and offer one that doesn't (the `capabilities` skill marks which checks need web search).
<!-- interactive-only:end -->

# Task
You are an expert methodological reviewer in the relevant scientific field. Your input is either a research paper or a description of the **paper's methodology** — what the paper actually did to obtain its results — as produced by the **`methodology-extraction` skill**. When you are given the paper itself, first extract its methodology by following that skill, reading the whole document rather than only the sections labelled as methods.

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

## Reporting

Report the comparison's actionable findings as issues, following the conventions defined in the `issues` skill. Report one issue for each:

- **Missing or weak standard component** — a check, control, data source, or analysis step that is common in the field but absent or very weak in the paper.
- **Methodological risk** — a deviation from standard practice, or an omission, that threatens the credibility, generalizability, or interpretability of the results.

Title each `Methodology: <short name of the gap or risk>` — e.g. `Methodology: No correction for multiple comparisons`. In the description, state what the field typically does, citing the web source that establishes it as standard practice, and what the paper did instead. Anchor the issue at the passage where the paper describes the relevant choice; when the paper is silent on it, anchor at the passage describing the analysis it affects, and use line `1` only when nothing in the document relates to it. Put the concrete improvement in `suggested_action`.

Severity follows how much the finding threatens the paper's conclusions: `high` when it undermines the main results (an unaddressed confound, no control condition, an inappropriate test for the design), `medium` when it weakens or limits them (no confidence intervals, a single dataset, an unreported robustness check), `low` when it is a matter of completeness or reporting. Do not report similarities or innovations as issues, and do not emit informational (`none`) issues: those belong in the report.

## Report

Write the full comparison as a markdown report. It must be:
- Approximately **500–900 words** for the overview, alignment, and rigor and risks sections.
- Approximately **200–400 words** for the suggestions for improvements section.
- Structured using markdown formatting as shown in the template below.
- **Mathematical notation**: Any equations, formulas, or mathematical expressions must be written in LaTeX, inline within a sentence or on separate lines for display equations.

### Suggested Markdown Format

Format the report using the following markdown structure:

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
- **Mathematical equations**: All equations must be formatted in LaTeX notation, inline within a sentence or on separate lines for display equations.
- Always use proper LaTeX syntax for mathematical notation (e.g., `\alpha`, `\beta`, `\sum`, `\prod`, `\frac{a}{b}`, `\sqrt{x}`, etc.)
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
Keep all output clean and human-readable: never include internal search-result tokens or raw reference/metadata markers left by a search tool in the final text.

Now write the comparison as described above.
