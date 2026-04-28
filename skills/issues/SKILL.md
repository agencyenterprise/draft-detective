---
name: issues
description: Use this skill whenever you need to report document review issues. It defines the standard issue format — field names, types, severity levels, line-number conventions, and best practices — used across all agent workflows in this project.
---

# Issues Reporting

## Overview

Every agent that identifies problems in a document must follow these output conventions precisely. This ensures issues are consistently structured and can be processed downstream.

## Issue Structure

Each problem must be reported as an issue with the following fields:

**`title`** (`str`)
A short, specific title that names the problem. If the instructions specify a title format for the rule, use it exactly, substituting any bracketed placeholders with the actual value (e.g. `"Figure/Table Missing Title: Figure 3"`, `"Author Bio Issue: Jane Smith"`). If no title is specified, create a concise one that clearly identifies the problem and the affected element. Good titles are scannable and self-explanatory.

**`description`** (`str`, markdown supported)
A 1–3 sentence explanation of the problem. Reference the specific text, element, or rule that failed. Explain what was expected and what was found. Do not invent content — base every judgment strictly on what is present in the document. Markdown formatting (bold, inline code, etc.) is supported and encouraged when it improves clarity.

**`severity`** (`"low"` | `"medium"` | `"high"`)
Choose based on impact on document quality:

- `"high"` — critical problems that significantly undermine document integrity: missing required sections, broken or unresolvable references, absent mandatory elements.
- `"medium"` — notable problems that reduce clarity or compliance: incomplete sections, unreferenced figures or tables, inconsistent numbering, rule violations that affect readability.
- `"low"` — minor issues with minimal impact: style suggestions, optional improvements, minor formatting inconsistencies.

When the workflow instructions specify a severity for a particular rule, always use that value.

**`start_line`** (`int`)
The 1-indexed line number in `/main.md` where the text relevant to this issue begins. Set to `1` when no specific location can be determined (e.g. a missing section that is absent from the entire document).

**`end_line`** (`int`)
The 1-indexed line number in `/main.md` where the relevant text ends. Must be ≥ `start_line`. Set to `1` when no specific location can be determined.

**`suggested_action`** (`str`, optional, markdown supported)
A direct, concise recommendation to the author on what to do to resolve this issue. Set this field whenever a concrete author-facing fix applies; omit it when no actionable recommendation can be made (e.g. for purely diagnostic findings).

The `suggested_action` is downstream-consumed: another agent will read the original document together with the issue and this field, and apply the change. Be specific enough that this is possible without further clarification — point to the exact location, name the element, and state the change in imperative form (e.g. *"Replace 'Figure 3' with 'Figure 2' on line 142 to match the figure caption."*, *"Add a citation supporting the sentence on line 88. Do not invent the citation — flag for the author to provide one."*).

**Critique, do not generate.** Suggest formulaic fixes (rewording, restructuring, pointing to where a citation is needed, fixing a numbering mismatch) but never fabricate content. Do not invent citations, references, data, or new prose paragraphs. For nuanced cases where the right fix requires author judgement, plain guidance text is acceptable (e.g. *"Add a citation to support this specific sentence — the author should select an appropriate source."*).

Keep it short — one or two sentences, or a tight bulleted list if multiple sub-steps are needed.

**`long_description`** (`str`, optional, markdown supported)
An extended markdown description for issues that require more detail than fits in `description`. Use this field only when the issue is complex enough that a short paragraph is not sufficient — for example, when you need to list multiple affected locations, quote specific passages, compare expected versus actual content, or provide step-by-step remediation guidance. If `description` alone communicates the problem clearly, omit this field entirely.

When used, format `long_description` with markdown to maximize readability:

- Use `##` or `###` headings to separate distinct sections (e.g. **What was found**, **What is expected**, **Affected locations**).
- Use bullet lists for enumerating multiple items.
- Use inline code or fenced code blocks to quote specific text from the document.
- Keep each section concise — the goal is clarity, not length.

## Issues List

Report one issue per problem found. Only create an issue for a failing rule or missing element — do not add entries for rules that pass.

## Line-Number Conventions

- Line numbers are 1-indexed: the first line of `/main.md` is line 1.
- For issues tied to a specific passage, set `start_line` and `end_line` to bracket that passage.
- For issues with no specific line or line range — for example, a finding that a required section is missing entirely from the document — set both `start_line` and `end_line` to `1`. **Never** report such an issue with a range that spans the entire document; a whole-document range is reserved for problems that genuinely apply to every line.

## Best Practices

- Report only genuine problems. Do not create issues for rules that pass.
- Each issue should be individually actionable — a reader should be able to locate the problem and fix it without further clarification.
- Descriptions must be grounded in the document content; never speculate or invent details.
- When multiple rules fail for the same element, create one issue per failed rule so each is independently actionable (unless the workflow instructions say otherwise).
