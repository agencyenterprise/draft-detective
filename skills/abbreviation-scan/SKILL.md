---
name: abbreviation-scan
description: Use this skill to check that a document's abbreviations and acronyms follow publication style — each is defined inline at its first use, listed in a dedicated Abbreviations section, used consistently, and not given conflicting meanings. Invoke when asked to review or validate a document's abbreviations/acronyms for compliance (e.g. per a manual of style).
---

# Abbreviation Scan

You are a document reviewer checking that abbreviations and acronyms follow publication style. Work in two steps: first **extract** every abbreviation occurrence, then **apply the compliance rules** to that catalogue.

## Step 1 — Extract

First, catalogue every abbreviation / acronym occurrence using the **`abbreviation-extraction` skill**. If the document's abbreviations have not already been extracted, extract them now using that skill. The catalogue gives you, for each occurrence: the abbreviation (in singular base form), any inline definition accompanying that occurrence, the occurrence count (1 = first appearance), where it appears, the definition listed in any Abbreviations section, and whether the occurrence is **excluded** from compliance checks (headings, References/Bibliography, cover page, and exempt classes such as titles, degrees, units, citation elements, ranks, equipment designators, all-caps corporation names, genus abbreviations, security markings, and "U.S.").

Treat excluded occurrences as out of scope: do **not** raise any issue for them. In addition, always treat these as excluded even if the extractor did not: **RAND**, **MIT**, **ChatGPT**.

## Step 2 — Apply the compliance rules

Evaluate the non-excluded occurrences against the rules below. Report **only genuine problems** — do not emit entries for abbreviations that pass, and do not report excluded occurrences. Every issue below is **severity: medium**. Use the abbreviation's "first use" to mean its **first non-excluded occurrence**.

If the document contains no abbreviations at all, report nothing.

### Rule 1 — Missing Abbreviations section
If the document uses at least one non-excluded abbreviation but has **no** dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section, report a single issue.
**Title:** "No Abbreviations section found"

### Rule 2 — Not defined at first use
At an abbreviation's **first** non-excluded occurrence, if there is **no** inline definition (the "Full Name (ABBR)" pattern), report an issue. Subsequent occurrences do not need an inline definition — never raise this for them.
**Title:** "Abbreviation not defined at first use"

### Rule 3 — Missing from the Abbreviations section
When a dedicated Abbreviations section **exists**, every non-excluded abbreviation should be listed in it. For each abbreviation that is **not** listed there, report **one** issue, located at its first non-excluded occurrence. Do not report it again for the abbreviation's later occurrences.
**Title:** "Abbreviation missing from Abbreviations section"

### Rule 4 — Inline definition does not match the Abbreviations section
At an abbreviation's first non-excluded occurrence, if it has an inline definition **and** is also listed in the Abbreviations section, but the two definitions differ (ignoring trivial case/whitespace/punctuation differences), report an issue.
**Title:** "Inline definition does not match Abbreviations section"

### Rule 5 — Ambiguous abbreviation
If an occurrence carries an inline definition that differs from the **first** inline definition recorded for that same abbreviation (ignoring trivial case/whitespace/punctuation differences), the document is using one abbreviation to mean more than one thing. Report an issue.
**Title:** "Ambiguous abbreviation"

## Reporting

Report issues following the conventions defined in the issues skill (`/skills/issues/SKILL.md`). Use the exact titles above and **severity: medium**. Set the issue's line range to the offending occurrence's location (for "No Abbreviations section found", which has no specific location, set both bounds to line 1). In each description, name the abbreviation and explain briefly what failed and what was expected. Do not invent content — base every judgment strictly on the extracted catalogue and the document.
