---
name: figures-tables-check
description: Use this skill to check that every figure and table in a document is properly titled/captioned, consistently numbered, referenced in the body text, and that all body-text references resolve to an actual figure or table. Invoke when asked to review or validate the figures and tables in a document for completeness and consistency.
---

# Figures & Tables Check

You are a specialist document reviewer. Review the document's figures and tables against the rules below and report any issues found. Read or search the document's content as needed to evaluate each rule.

## Rules

Evaluate the document against **every** rule below. For each rule that **fails**, report one issue. For rules that pass, do **not** create an issue.

### Rule 1 — Every figure/table has a title or caption

Every figure and every table in the document must have a descriptive title or caption directly associated with it. Look for labels such as "Figure X:", "Fig. X:", "Table X:" followed by a caption or title string.

**If any figure or table has no title or caption → issue title:** "Figure/Table Missing Title: [label]" (Create one issue per offending figure/table.)

### Rule 2 — All figures and tables are numbered consistently

All figures must follow one numbering scheme throughout the document, and all tables must follow one numbering scheme throughout the document.

Accepted schemes (any is valid; mixing within the same element type is not):

- **Sequential**: Figure 1, Figure 2, Figure 3 … (or Table 1, Table 2 …). Supplementary items may be numbered separately as Figure S1, S2 … or Table S1, S2 …
- **By chapter**: Figure 4.1, Figure 4.2 … (or Table 4.1, Table 4.2 … where the first digit is the chapter number)
- **By section / appendix prefix**: items carry the prefix of the section or appendix they belong to — e.g. Figure A.1, A.2 … in Appendix A, Figure B.1, B.2 … in Appendix B, or Table 3.1, 3.2 … in Chapter 3. The prefix (a letter for an appendix, a digit for a chapter) just identifies the section; the trailing number is the sequence within it.

Flag the document if:

- Numbering skips values without explanation (e.g. Figure 1, Figure 3 with no Figure 2 anywhere; or Figure A.1, A.3 with no A.2 in Appendix A)
- A genuinely arbitrary mix appears within the same element type and section — e.g. plain sequential Figure 1, Figure 2 interleaved with an unrelated Figure 3.1 in the *same* body section, where 3.1 does not correspond to any chapter or appendix prefix
- An appendix/section prefix does not match its section (e.g. figures in Appendix B numbered A.1, A.2)
- A figure or table has no number at all

**If inconsistent numbering is found → issue title:** "Inconsistent Numbering: [brief description]"

### Rule 3 — Every figure/table is referenced in the body text

Every figure and table that appears in the document must be cited at least once in the body text (e.g. "see Figure 3", "as shown in Table 2", "(Table S1)"). Cross-references in captions of other figures/tables do not count as body text references.

**If a figure or table is never mentioned in the body → issue title:** "Unreferenced Figure/Table: [label]" (Create one issue per unreferenced figure/table.)

### Rule 4 — Every figure/table mentioned in the body is present in the document

Every figure and table cited in the body text must actually exist in the document. Check that each reference of the form "Figure X", "Fig. X", "Table X" etc. has a corresponding labelled figure or table.

**If a referenced figure/table is absent from the document → issue title:** "Missing Figure/Table: [label referenced in text]" (Create one issue per missing figure/table.)

## Viewing figures

A figure's content may be an embedded image, or it may be given as a table, a code block or text under the figure's caption. A figure is present when any content for it is present: how it is rendered is not a rule, and a figure must never be reported as missing merely because it has no image. When you have a way to view images, look at an actual image whenever seeing it would change your judgment:

- To tell whether an image is a genuine figure (chart, diagram, map, photo of results) or a decorative element (logo, banner, cover art, signature). **Decorative images are not figures — do not flag them under any rule.**
- To confirm that an image near a caption is really the exhibit the caption describes (Rule 1). An image that is only a blank box or a placeholder ("chart to be inserted", "TBD") is not the figure: the figure the caption and body refer to is missing (Rule 4).
- When a figure label or caption appears with no image nearby, or an image appears with no caption — check the image before reporting, since the caption may be rendered inside the image itself.

A table given as text needs no image viewing; a table rendered as an image is judged like a figure. If an image cannot be viewed (no image-viewing capability, unsupported format, missing file), evaluate the rules from the image's alt text and the surrounding text instead.

## Exclusion — Abbreviation / Acronym tables

Many documents contain a dedicated **Abbreviations**, **Acronyms**, or **List of Abbreviations** section. This section typically presents a two-column table (abbreviation | definition) or a simple definition list and is **not** a regular numbered figure or table.

**Exclude these abbreviation/acronym tables from all rules above.** Do not flag them for missing titles, missing numbers, missing body-text references, or any other rule. They are cataloguing tools, not data exhibits, and are handled by a separate analysis.

## Reporting

For each rule that fails, report one issue following the conventions defined in the `issues` skill. Do not create issues for rules that pass.
