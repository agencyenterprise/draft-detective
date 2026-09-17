---
name: issues
description: Use this skill to report document review findings with clear evidence, severity, and actionable guidance. Present findings naturally in chat and written reviews; use the standard issue schema when a workflow, tool, or user requires structured output.
---

# Issues Reporting

## Overview

Keep findings grounded in the document, explain why each problem matters, and give a concrete next step when possible. The reporting format depends on the deliverable.

## Choose the Reporting Format

- **Explicit output requirements take precedence, including in chat:** when the user, task skill, or workflow requires issue fields, a structured response, or an issue-reporting tool, follow that contract using the field names, types, and conventions below. A conversational interface does not waive these requirements.
- **Chat and written reviews without a required schema:** use readable prose, bullets, or headings suited to the request.
- **Both:** submit the required structured records, then use natural language for any accompanying user-facing explanation. A readable summary does not replace required tool calls or structured output.

Instructions such as "report one issue per missing section" determine which findings to report and how to separate them; they do not alone prescribe a field-by-field layout. Another skill's reference to these conventions preserves its required titles, severity, evidence, locations, and one-finding-per-item rules in either format. Use structured records when that skill also requires issue fields or a schema; otherwise, present each finding naturally.

## Conversational Findings

Make each finding easy to locate and act on: identify the passage or element, explain the problem and its impact, and suggest a fix. Use a short quote, section, page, or available line number to anchor it. Do not invent line numbers or display the structured fallback of line 1 for an unlocated finding.

Mention severity in ordinary language when it helps prioritize the review, using the severity scale below and any task-specific severity. Keep required rule titles and classifications, but integrate them into readable headings or prose. Avoid raw schema labels such as `start_line`, `suggested_action`, or `replacement_text` unless structured output was requested.

When a wording change is justified by the document, show the suggested wording once and explain it briefly. Do not repeat the same passage as a suggestion and again as an edit record. Apply the same evidence and no-fabrication standards as structured findings; leave decisions requiring new facts or author judgment to the author.

For example, a chat finding could read:

> **Passive voice (minor suggestion, line 11).** “Those decisions are being made” leaves the actor unnamed, though the surrounding text identifies agency leaders. Consider “Agency leaders are making those decisions…” to make the actor explicit.

This is an illustration, not a required template. Use the amount of structure and detail the request needs.

## Structured Issue Output

The field schema and line-number conventions in this section apply to structured records, not to the layout of chat replies. Each problem must be reported with the following fields:

**`title`** (`str`)
A short, specific title that names the problem. If the instructions specify a title format for the rule, use it exactly, substituting any bracketed placeholders with the actual value (e.g. `"Figure/Table Missing Title: Figure 3"`, `"Author Bio Issue: Jane Smith"`). If no title is specified, create a concise one that clearly identifies the problem and the affected element. Good titles are scannable and self-explanatory.

**`description`** (`str`, markdown supported)
A 1–3 sentence explanation of the problem. Reference the specific text, element, or rule that failed. Explain what was expected and what was found. Do not invent content — base every judgment strictly on what is present in the document. Markdown formatting (bold, inline code, etc.) is supported and encouraged when it improves clarity.

**`severity`** (`"none"` | `"low"` | `"medium"` | `"high"`)
Choose based on impact on document quality:

- `"high"` — critical problems that significantly undermine document integrity: missing required sections, broken or unresolvable references, absent mandatory elements.
- `"medium"` — notable problems that reduce clarity or compliance: incomplete sections, unreferenced figures or tables, inconsistent numbering, rule violations that affect readability.
- `"low"` — minor issues with minimal impact: style suggestions, optional improvements, minor formatting inconsistencies.
- `"none"` — **informational, opt-in only.** Use exclusively when the workflow's user prompt explicitly asks you to surface valid / passing checks alongside problems (e.g. confirming a recommendation is well-grounded, attesting that a section meets a rule). Never emit `"none"` issues unless the workflow instructions request them — by default, do not create entries for rules that pass.

When the workflow instructions specify a severity for a particular rule, always use that value.

**`start_line`** (`int`)
The 1-indexed line number in the supplied document where the text relevant to this issue begins. Set to `1` when no specific location can be determined (e.g. a missing section that is absent from the entire document).

**`end_line`** (`int`)
The 1-indexed line number in the supplied document where the relevant text ends. Must be ≥ `start_line`. Set to `1` when no specific location can be determined.

**`suggested_action`** (`str`, optional, markdown supported)
A direct, concise recommendation to the author on what to do to resolve this issue. Set this field whenever a concrete author-facing fix applies; omit it when no actionable recommendation can be made (e.g. for purely diagnostic findings).

The `suggested_action` is downstream-consumed: another agent will read the original document together with the issue and this field, and apply the change. Be specific enough that this is possible without further clarification — point to the exact location, name the element, and state the change in imperative form (e.g. *"Replace 'Figure 3' with 'Figure 2' on line 142 to match the figure caption."*, *"Add a citation supporting the sentence on line 88. Do not invent the citation — flag for the author to provide one."*).

**Critique, do not generate.** Suggest formulaic fixes (rewording, restructuring, pointing to where a citation is needed, fixing a numbering mismatch) but never fabricate content. Do not invent citations, references, data, or new prose paragraphs. For nuanced cases where the right fix requires author judgement, plain guidance text is acceptable (e.g. *"Add a citation to support this specific sentence — the author should select an appropriate source."*).

Keep it short — one or two sentences, or a tight bulleted list if multiple sub-steps are needed.

**`edits`** (list, optional; only when the workflow enables proposed edits)
Zero or more mechanical text replacements that resolve the issue. An edit is the structured form of `suggested_action`: it says exactly which characters to swap, so the fix can be applied without re-reading the document. Each edit has:

- **`original_text`** (`str`, required) — the text to replace, quoted **verbatim** from the document. It must appear exactly once inside the issue's `start_line`–`end_line` range; if a short quote repeats, widen it (up to the whole line) so it is unique and make the change inside it. It must sit within a single line of the document — an edit never crosses a line break, so it stays inside one paragraph.
- **`replacement_text`** (`str`, required) — the text that takes its place. Use an empty string to delete the quoted text. To insert text, repeat the quoted text with the addition included (e.g. replace `"the results in Table 2"` with `"the results in Table 2 and Table 3"`).
- **`rationale`** (`str`, required) — one short sentence on why this replacement resolves the issue.

**Propose an edit only when the fix is fully determined by the document text plus the finding.** Never propose one when the fix needs a new fact or new prose: no invented citations, references, data, findings, or rewritten paragraphs. If the right fix requires the author's judgement or information that is not in the document, leave `edits` empty and say what is needed in `suggested_action`.

Attaching edits does not replace `suggested_action` — set both. One issue may carry several edits when a single finding requires more than one replacement, each within its own line. If nothing about the fix is mechanical, omit `edits` entirely; an issue with no edits is a normal, complete issue.

**`long_description`** (`str`, optional, markdown supported)
An extended markdown description for issues that require more detail than fits in `description`. Use this field only when the issue is complex enough that a short paragraph is not sufficient — for example, when you need to list multiple affected locations, quote specific passages, compare expected versus actual content, or provide step-by-step remediation guidance. If `description` alone communicates the problem clearly, omit this field entirely.

When used, format `long_description` with markdown to maximize readability:

- Use `##` or `###` headings to separate distinct sections (e.g. **What was found**, **What is expected**, **Affected locations**).
- Use bullet lists for enumerating multiple items.
- Use inline code or fenced code blocks to quote specific text from the document.
- Keep each section concise — the goal is clarity, not length.

### Structured Issues List

Report one issue per problem found. Only create an issue for a failing rule or missing element — do not add entries for rules that pass, **unless** the workflow's user prompt explicitly asks you to surface passing checks as informational (`severity: "none"`) items.

### Structured Line-Number Conventions

- Line numbers are 1-indexed: the first line of the supplied document is line 1. Use the workflow's designated document and line numbering.
- For issues tied to a specific passage, set `start_line` and `end_line` to bracket that passage.
- For issues with no specific line or line range — for example, a finding that a required section is missing entirely from the document — set both `start_line` and `end_line` to `1`. **Never** report such an issue with a range that spans the entire document; a whole-document range is reserved for problems that genuinely apply to every line.

## Best Practices for All Formats

- Report only genuine problems. Do not create issues for rules that pass, unless the workflow instructions explicitly request informational (`severity: "none"`) entries for passing checks.
- Each issue should be individually actionable — a reader should be able to locate the problem and fix it without further clarification.
- Descriptions must be grounded in the document content; never speculate or invent details.
- When multiple rules fail for the same element, create one issue per failed rule so each is independently actionable (unless the workflow instructions say otherwise).
