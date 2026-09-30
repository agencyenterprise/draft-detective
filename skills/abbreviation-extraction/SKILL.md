---
name: abbreviation-extraction
description: Use this skill to find and catalogue every abbreviation and acronym occurrence in a document — recording, for each occurrence, any accompanying inline definition, how many times the abbreviation has appeared so far, where it appears, and the definition listed in any Abbreviations section, leaving out occurrences that are exempt from compliance checks. Invoke when asked to extract, list, or inventory the abbreviations/acronyms in a document (e.g. as input to an abbreviation compliance check).
---

# Abbreviation Extraction

You are a meticulous document analyst specialising in identifying and cataloguing abbreviations and acronyms.

## Your task

Scan the **entire** document and produce a complete catalogue of every abbreviation / acronym occurrence that a compliance check applies to. Occurrences that are exempt (see **Occurrences not to record**) are left out of the catalogue entirely. You are **not** checking compliance rules here — your job is to record accurate, complete data for every occurrence so that a downstream check has everything it needs.

For each occurrence, capture:

- **The abbreviation itself** (e.g. "OUSW").
- **Any inline definition accompanying that specific occurrence** — i.e. the pattern "Full Name (ABBR)". For example, "The Office of the Under Secretary of War (OUSW) issued…" has an inline definition, while a later bare "OUSW" does not. Record an empty value when the occurrence has no inline definition immediately accompanying it.
- **The occurrence count** — how many times this abbreviation has been recorded so far in the document (1 for the first recorded appearance, 2 for the second, and so on). Occurrences that are not recorded do not count. The first occurrence is the most important.
- **Where the occurrence appears** — the line range in the document where it occurs (for a single-line occurrence, the start and end are the same line).
- **The definition listed in any dedicated Abbreviations section** — if the document has an "Abbreviations", "Acronyms", "Glossary", or equivalent section and this abbreviation is listed there, record the definition as written there; otherwise record that it is absent.

## How to proceed

1. **Find the Abbreviations section first.** Look for a dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section and build a map of every abbreviation defined there together with its listed definition.

2. **Read the document from the beginning, section by section.** On **every line**, identify **all** abbreviations present that are not exempt — including ones you have already seen earlier in the document. Do not skip an abbreviation just because it was recorded on a previous line. For each occurrence, record the abbreviation, the inline definition accompanying that exact occurrence (empty if none), the occurrence count, the line range, and the definition from the Abbreviations-section map (absent if not listed there or if no such section exists).

3. **Read the entire document — do not stop early.**

## One entry per occurrence

Produce one entry per **occurrence**, not one per unique abbreviation. If the same abbreviation appears 10 times, there should be 10 entries with occurrence counts 1–10. A single line may contain multiple abbreviations — both different abbreviations and repeated uses of the same one — and **every** abbreviation on a line must be recorded as its own entry. For example, "The NATO task force and the OSCE delegation briefed NATO headquarters" produces three entries (NATO, OSCE, NATO), all sharing the same line range.

## Plural forms

Treat the plural form of an abbreviation as the same abbreviation as its singular form. For example, "LLMs" is the plural of "LLM" — they are the same abbreviation. Always record the singular base form (e.g. "LLM", not "LLMs"). Occurrence counting, inline-definition recording, and Abbreviations-section lookups all treat singular and plural as a single abbreviation, and a definition on either form counts for both (e.g. "Large Language Models (LLMs)" satisfies the first-use definition for "LLM").

## Occurrences not to record

Leave these occurrences out of the catalogue entirely. They are not compliance-checked, so they must not appear even as flagged or excluded entries, and they do not count toward occurrence numbers.

- **Heading abbreviations** — any abbreviation appearing inside a Markdown heading (a line starting with one or more `#` characters).
- **References / Bibliography section** — any abbreviation appearing inside a dedicated "References", "Bibliography", "Works Cited", or equivalent section.
- **Front page / cover page** — any abbreviation appearing on the front or cover page (typically the first page, before the table of contents or any body section).
- **Footnotes and endnotes** — any abbreviation appearing inside the text of a footnote or endnote: the numbered notes at the foot of a page, collected at the end of a chapter, or gathered in a "Notes" / "Endnotes" section (e.g. lines such as `12 Kyle Orland, "…," Ars Technica, 2017.` or `[^12]: …`). Notes are citation apparatus, not body text. Only the note's own text is skipped: the sentence in the body that carries the note marker is recorded as usual.
- **Lists of figures and tables** — the entries of a "List of Figures", "List of Tables", "Figures and Tables", or equivalent list, which repeat the titles of the document's figures and tables. The figures, tables and captions themselves are recorded as usual: an abbreviation used only in a table or caption still needs its definition.
- **The Abbreviations / Glossary section itself** — the dedicated "Abbreviations", "Acronyms", "Glossary", or equivalent section is the reference list, not document body text. (Its contents are still used to populate each recorded occurrence's "definition listed in the Abbreviations section".)
- **URLs** — abbreviations inside a URL or web address, including a link whose visible text is itself an address, e.g. the "CAST" in `[www.rand.org/CAST](http://www.rand.org/CAST)`. A link whose visible text is ordinary prose (e.g. `[the NATO report](https://…)`) is recorded as usual; only the address itself is skipped.
- **Always-excluded names** — **RAND**, **MIT** and **ChatGPT**, wherever they appear.
- **Exempt abbreviation classes** — abbreviations that clearly belong to one of these common classes:

| Class | Examples | Notes |
|---|---|---|
| Personal titles | Mr., Mrs., Ms., Dr., Rev., Hon. | |
| Academic degrees | Ph.D., M.A., B.Sc., M.D., J.D. | |
| Common units of measurement | cm, mm, km, mW, kHz, MHz, GHz, kg, mg | |
| Citation elements | Vol., Ch., pp., para., ed., ibid., et al. | |
| Legal and regulatory citations | U.S.C., C.F.R., Stat., Pub. L., Fed. Reg. | As part of a citation such as "10 U.S.C. 2350" |
| Latin and common shorthand | e.g., i.e., etc., cf., vs., viz., approx., no., ID | "no." as in "No. 12", not the word "no"; "ID" as in "item IDs" |
| Statistical notation | N, n, M, SD, SE, R², R2, p, t, F, F1, df, Std. Dev. | When used as notation for a statistic, e.g. "N = 120", "Pseudo R2", an "F1" column |
| Numeric magnitude suffixes | $9.6B, 10M, 5K, $1T | The letter attached to a number, meaning billion, million, thousand, trillion |
| U.S. state and territory postal codes | CA, FL, NM, NY, UT, VA | In an address or place name, e.g. "Riverside, CA"; a postal code used on its own as a term is not exempt |
| Product, model, and software names | GPT-4, XGBoost, OpenAI, Llama 3 | Names used as names. Benchmark and dataset acronyms (MMLU, GPQA, WMDP) are abbreviations, not names: record them like any other |
| Document and report identifiers | M-25-21, RR-A4036-1, TR-3 | Catalogue, memo, or report numbers |
| Military ranks | Col., Gen., Sgt., Lt., Cpl., Adm., Maj. | |
| Military equipment designators | C-141, F-35, Su-35, M-1, Ka-32 | |
| Corporation names (all-caps) | RAND, CNA, MITRE, IBM, SAIC | |
| Biological genus abbreviations | E. coli, C. botulinum, S. aureus | |
| Security markings | (U), (S), (C), (TS), (SCI) | Portion markings in parentheses |
| Country abbreviations | U.S., US, UK | When they stand for the country, e.g. "U.S. forces", "the UK AI Security Institute" |

## Output

Return the full catalogue (one entry per occurrence, as described above), whether or not a dedicated Abbreviations (or equivalent) section was found, and a brief summary of what you found and how.
