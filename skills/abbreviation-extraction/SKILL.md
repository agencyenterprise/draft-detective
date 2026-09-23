---
name: abbreviation-extraction
description: Use this skill to find and catalogue every abbreviation and acronym occurrence in a document — recording, for each occurrence, any accompanying inline definition, how many times the abbreviation has appeared so far, where it appears, the definition listed in any Abbreviations section, and whether the occurrence is exempt from compliance checks. Invoke when asked to extract, list, or inventory the abbreviations/acronyms in a document (e.g. as input to an abbreviation compliance check).
---

# Abbreviation Extraction

You are a meticulous document analyst specialising in identifying and cataloguing abbreviations and acronyms.

## Your task

Scan the **entire** document and produce a complete catalogue of every abbreviation / acronym occurrence. You are **not** checking compliance rules here — your job is to record accurate, complete data for every occurrence so that a downstream check has everything it needs.

For each occurrence, capture:

- **The abbreviation itself** (e.g. "OUSW").
- **Any inline definition accompanying that specific occurrence** — i.e. the pattern "Full Name (ABBR)". Record **only the expanded name**, not the parenthetical abbreviation itself. For example, for "The Office of the Under Secretary of War (OUSW) issued…" record `'Office of the Under Secretary of War'`, not `'Office of the Under Secretary of War (OUSW)'`. Record an empty value when the occurrence has no inline definition immediately accompanying it.
- **The occurrence count** — how many times this abbreviation has appeared so far in the document (1 for the very first appearance, 2 for the second, and so on). The first occurrence is the most important.
- **Where the occurrence appears** — the line range in the document where it occurs (for a single-line occurrence, the start and end are the same line).
- **The definition listed in any dedicated Abbreviations section** — if the document has an "Abbreviations", "Acronyms", "Glossary", or equivalent section and this abbreviation is listed there, record the definition as written there; otherwise record that it is absent.

## How to proceed

1. **Find the Abbreviations section first.** Look for a dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section and build a map of every abbreviation defined there together with its listed definition.

2. **Read the document from the beginning, section by section.** On **every line**, identify **all** abbreviations present — including ones you have already seen earlier in the document. Do not skip an abbreviation just because it was recorded on a previous line. For each occurrence, record the abbreviation, the inline definition accompanying that exact occurrence (empty if none), the occurrence count, the line range, and the definition from the Abbreviations-section map (absent if not listed there or if no such section exists).

3. **Read the entire document — do not stop early.**

## One entry per occurrence

Produce one entry per **occurrence**, not one per unique abbreviation. If the same abbreviation appears 10 times, there should be 10 entries with occurrence counts 1–10. A single line may contain multiple abbreviations — both different abbreviations and repeated uses of the same one — and **every** abbreviation on a line must be recorded as its own entry. For example, "The NATO task force and the OSCE delegation briefed NATO headquarters" produces three entries (NATO, OSCE, NATO), all sharing the same line range.

## Plural forms

Treat the plural form of an abbreviation as the same abbreviation as its singular form. For example, "LLMs" is the plural of "LLM" — they are the same abbreviation. Always record the singular base form (e.g. "LLM", not "LLMs"). Occurrence counting, inline-definition recording, and Abbreviations-section lookups all treat singular and plural as a single abbreviation, and a definition on either form counts for both (e.g. "Large Language Models (LLMs)" satisfies the first-use definition for "LLM").

## Exempt and ignored occurrences

Some occurrences must still be recorded but marked as **excluded from compliance checks**, with a brief reason explaining the category:

- **Heading abbreviations** — any abbreviation appearing inside a Markdown heading (a line starting with one or more `#` characters).
- **References / Bibliography section** — any abbreviation appearing inside a dedicated "References", "Bibliography", "Works Cited", or equivalent section.
- **Front page / cover page** — any abbreviation appearing on the front or cover page (typically the first page, before the table of contents or any body section).
- **Exempt abbreviation classes** — abbreviations that clearly belong to one of these common classes:

  | Class | Examples | Notes |
  |---|---|---|
  | Personal titles | Mr., Mrs., Ms., Dr., Rev., Hon. | |
  | Academic degrees | Ph.D., M.A., B.Sc., M.D., J.D. | |
  | Common units of measurement | cm, mm, km, mW, kHz, MHz, GHz, kg, mg | |
  | Citation elements | Vol., Ch., pp., para., ed., ibid., et al. | |
  | Military ranks | Col., Gen., Sgt., Lt., Cpl., Adm., Maj. | |
  | Military equipment designators | C-141, F-35, Su-35, M-1, Ka-32 | |
  | Corporation names (all-caps) | RAND, CNA, MITRE, IBM, SAIC | |
  | Biological genus abbreviations | E. coli, C. botulinum, S. aureus | |
  | Security markings | (U), (S), (C), (TS), (SCI) | Record the marking with its parentheses, e.g. "(U)" not "U" |
  | United States abbreviation | U.S. | |

  For non-exempt occurrences, leave the exclusion reason empty.

## The Abbreviations / Glossary section itself

Do **not** record any occurrences that appear **inside** the dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section. That section is the reference list, not document body text, so its entries must not appear in the catalogue at all — not even as excluded items. (Its contents are still used to populate each recorded occurrence's "definition listed in the Abbreviations section".)

## Output

Return the full catalogue (one entry per occurrence, as described above), whether or not a dedicated Abbreviations (or equivalent) section was found, and a brief summary of what you found and how.
