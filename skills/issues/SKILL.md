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

**`long_description`** (`str`, optional, markdown supported)
An extended markdown description for issues that require more detail than fits in `description`. Use this field only when the issue is complex enough that a short paragraph is not sufficient — for example, when you need to list multiple affected locations, quote specific passages, compare expected versus actual content, or provide step-by-step remediation guidance. If `description` alone communicates the problem clearly, omit this field entirely.

When used, format `long_description` with markdown to maximise readability:

- Use `##` or `###` headings to separate distinct sections (e.g. **What was found**, **What is expected**, **Affected locations**).
- Use bullet lists for enumerating multiple items.
- Use inline code or fenced code blocks to quote specific text from the document.
- Keep each section concise — the goal is clarity, not length.

## Issues List

Report one issue per problem found. Only create an issue for a failing rule or missing element — do not add entries for rules that pass.

## Line-Number Conventions

- Line numbers are 1-indexed: the first line of `/main.md` is line 1.
- For issues tied to a specific passage, set `start_line` and `end_line` to bracket that passage.
- For document-level issues where a section or element is entirely absent, use the line range of the area where it should appear (e.g. the beginning of the document, or the location of the nearest related section).
- When no meaningful location exists, set both `start_line` and `end_line` to `1`.

## Best Practices

- Report only genuine problems. Do not create issues for rules that pass.
- Each issue should be individually actionable — a reader should be able to locate the problem and fix it without further clarification.
- Descriptions must be grounded in the document content; never speculate or invent details.
- When multiple rules fail for the same element, create one issue per failed rule so each is independently actionable (unless the workflow instructions say otherwise).
