---
name: reference-validation
description: Use this skill to validate a bibliographic reference (journal article, preprint, book, webpage, press release, government report, etc.) by searching for it online and comparing the citation to authoritative sources. Invoke when the user asks to check, verify, fact-check, or validate a citation or list of references — confirming author, title, publisher, year, and identifier (DOI / arXiv ID / ISBN / ISSN) against the actual published work.
---

# Reference Validation

Validate a single bibliographic reference by finding the cited work online and comparing it to the reference. Follow the six-step procedure below for each reference. Web search (or URL fetching) is required — never validate from memory.

If the user provides multiple references, repeat the procedure for each one and report results per reference.

## Step 1 — Parse the reference

Read the reference and note:
- What type of work it is (journal article, preprint, book, webpage, press release, government report, briefing slides, etc.).
- Which fields are present: author, title, publisher/venue, year, identifier (DOI, arXiv ID, ISBN, ISSN), URL.

Special case — bare URL: if the reference is only a URL with no bibliographic metadata, skip ahead to Step 6 with final result `missing_fields`. Reconstruct the full citation from the URL's content and populate `updated_reference`. Mark author, title, publisher, and year as MISSING; mark `identifier` as CORRECT (identifier is always optional).

## Step 2 — Resolve the URL (if the reference contains one)

Fetch the URL exactly as given. One of three outcomes:

- URL resolves to real content that appears to match the reference → use that page as your primary authoritative source. Continue to Step 4.
- URL resolves but the page is clearly unrelated (a different article, a generic landing page) → note the URL as inconsistent. Continue to Step 3 to search.
- URL returns 404 or error → the URL is inconsistent or fabricated. Continue to Step 3.

Do NOT treat a URL as valid just because its domain/path looks plausible — you must confirm the page actually exists and has real content.

## Step 3 — Search the web for the cited work

Search using the reference's title (quote distinctive phrases) together with a key author surname and/or year. For references with a DOI or arXiv ID, resolve the identifier first and use the canonical page — BUT if the resolved work's title clearly does not match the reference's title, treat the identifier as incorrect or fabricated and search by title instead. Do NOT accept an unrelated work as your candidate just because an identifier happened to resolve to it; when this happens, flag the identifier as INCORRECT in Step 5 and use the title-based candidate for the other fields.

Pick the single best candidate that plausibly IS the cited work. If no candidate matches the cited title or authors, stop and go to Step 6 with `incorrect_fields` (a reference that cannot be located online is treated as a substantive issue).

ArXiv-specific rules:
- ArXiv versioning: when the reference cites an arXiv paper WITHOUT a version suffix (e.g., `arXiv:2311.16169` rather than `arXiv:2311.16169v1`), treat the MOST RECENT version on arXiv as authoritative — its title, author list, and most-recent submission year. When the reference explicitly pins a version (e.g., `arxiv.org/abs/2406.01637v1`), treat that version as authoritative instead.
- ArXiv HTML view: URLs of the form `arxiv.org/html/...` sometimes contain rendering artifacts that produce incorrect-looking titles. Do not take the title from the HTML view. Prefer, in order: (a) the title from the official conference/journal publication if one exists, (b) the arXiv abstract page `arxiv.org/abs/...`, (c) the PDF.
- ArXiv + official publication: if a paper has both an arXiv preprint and an official conference/journal publication (e.g., IEEE S&P, ACM CSCW, NeurIPS), the official venue is the preferred publisher; the arXiv ID remains a valid identifier.

## Step 4 — Decide whether the candidate is the same work

Before comparing fields, confirm the candidate source IS the cited work. Compare the candidate's title to the reference's title, ignoring case and punctuation:

- Titles match in wording → it is the SAME WORK. Proceed to Step 5. (Any disagreements in author, publisher, or year are attribution errors in the citation, not a mis-match.)
- Titles clearly differ in wording AND two or more of {author, publisher, year} also differ → the candidate is a DIFFERENT WORK on a related topic. Go to Step 6 with `incorrect_fields`. Do not try to "rescue" a bad reference by treating a different work as a match.
- Titles differ but author, publisher, and year all line up → likely the same work under a retitling or reprinting. Treat as same work and continue to Step 5.

## Step 5 — Compare each field

For each of author, title, publisher, year, identifier, set `problem_type` to one of `correct`, `missing`, `incorrect`, or `other`:

- CORRECT — the reference matches the authoritative source in substance. Apply CORRECT when the only differences are:
  * Capitalization (title case vs sentence case vs all caps)
  * Punctuation (commas, periods, hyphens/dashes, colons, quotation marks, trailing separators)
  * Author name form (full first name vs initial, middle initial present/absent, surname particles like "von"/"de"/"van" present/absent)
  * Truncated author lists (the reference lists the first N authors, with or without "et al.", while the full work has more authors — this is a valid citation style, not an error)
  * Organization form (well-known abbreviation vs full name — e.g., "ACM" = "Association for Computing Machinery", "DMDC" = "Defense Manpower Data Center"; current brand vs recent rebrand — e.g., "Raytheon Technologies" = "RTX")
  * Field ordering
  * Page ranges (ignore entirely)
- MISSING — the field is absent from the reference but exists for the work.
- INCORRECT — the reference contains substantively different content: different words, different people, wrong numbers, wrong dates, historically incorrect names (e.g., a pre-1947 government title used to cite a modern agency).

Field-specific notes:
- **Title**: use the title that appears in the main content body of the authoritative page — the `<h1>` heading, the article headline, or the title page of a PDF. Do NOT use the browser tab `<title>` tag, the `og:title` social-sharing title, or a search-engine snippet — these are often shortened or sanitized. For PDF-linked articles, prefer the title inside the PDF.
- **Year**: mark CORRECT when the cited year is within ±1 of the authoritative publication year. This tolerance covers the common arXiv-preprint vs. conference-publication off-by-one case and minor in-press/issue-date disagreements. Use INCORRECT only when the gap is larger than one year. For books and book chapters specifically, accept the year of ANY published edition (print, electronic, paperback reprints, etc.) — e.g., if a book has a 2006 print edition and a 2009 electronic edition, either year is CORRECT.
- **Publisher**: substring matches and well-known abbreviations or shortened forms are CORRECT as long as a reader can still recognize the publisher (e.g. "ACM" = "Association for Computing Machinery", "Springer" = "Springer Nature", "MIT Press" = "The MIT Press"). Use INCORRECT only when the publisher names refer to different organizations.
- **Identifier**: identifier is ALWAYS OPTIONAL. A DOI, arXiv ID, ISBN, or ISSN all qualify. If the reference includes one, check it resolves to the correct work; flag INCORRECT only if it resolves to a different work or is fabricated. If the reference omits an identifier, mark CORRECT (never MISSING) — you MAY populate `suggested_value` with a known DOI, arXiv ID, ISBN, or ISSN when one exists, but NEVER suggest a URL as an identifier. Accept equivalent forms: a URL that resolves to a persistent identifier (e.g., `https://doi.org/10.xxxx/...`, `https://dl.acm.org/doi/pdf/10.xxxx/...`, `https://arxiv.org/abs/...`) is equivalent to the bare identifier. A missing DOI when an arXiv ID is already present is NOT an error.
- **Author**: either personal author names OR an institutional/organizational name are acceptable as the author field. If the reference lists individual authors and the work is also attributable to the publishing organization (or vice versa), treat as CORRECT — do not demand the other form. Only mark INCORRECT when the listed author(s) are substantively wrong (different people, or an institution that did not publish the work). For institutional works (press releases, homepages, government reports, briefing slides, datasets, policy directives), the org name as author is fully acceptable.

## Step 6 — Decide the final result

`final_result` is mechanical given the per-field `problem_type`s from Step 5. Apply in order:

1. No candidate found, OR candidate is a different work (per Step 4) → `final_result = "incorrect_fields"`. A reference that cannot be located online is treated as a substantive (red) issue. Set `updated_reference = null`.
2. Same work and at least one field has `problem_type = INCORRECT` → `final_result = "incorrect_fields"`. Populate `updated_reference` with the corrections applied, preserving the reference's original citation style.
3. Same work, no INCORRECT fields, and at least one field has `problem_type = MISSING` → `final_result = "missing_fields"`. Populate `updated_reference` if there is a useful correction to suggest; otherwise set it to `null`.
4. Same work and every field has `problem_type = CORRECT` → `final_result = "correct"`. Set `updated_reference = null`.

All leniency belongs at the field level in Step 5 (case/punctuation, name forms, truncated author lists, organizational abbreviations, year ±1, publisher substring/abbreviation, identifier URL forms, missing-identifier-with-clear-venue). Apply that leniency when assigning each field's `problem_type`, then derive `final_result` mechanically from the rules above. Do NOT add any extra "default to correct on the boundary" softening at the result level.

## Output

For each validated reference, report the following structure (JSON or a clearly-formatted markdown block — match whatever the user asked for; default to markdown):

- `original_reference` — the reference as given.
- `final_result` — one of `correct`, `missing_fields`, `incorrect_fields`.
  * `correct` — every field verified against an authoritative source (green).
  * `missing_fields` — at least one field MISSING but none INCORRECT (yellow).
  * `incorrect_fields` — at least one field INCORRECT, OR the reference could not be found online (red).
- `bibliography_field_validations` — one entry per field (`author`, `title`, `publisher`, `year`, `identifier`) with:
  * `category` — the field name.
  * `current_value` — the value as it appears in the reference.
  * `suggested_value` — the authoritative value.
  * `problem_type` — `correct` / `missing` / `incorrect` / `other`. (Use `correct` when the only differences are capitalization or minor punctuation.)
- `url` — the URL identifying the cited work (from the reference, identifier resolution, or your search). Empty string when no candidate was found.
- `reasoning` — a brief step-by-step summary of how you validated.
- `suggested_action` — one sentence describing what to fix; `"No changes needed"` when `correct`.
- `updated_reference` — corrected citation in the reference's original format when there are corrections to suggest (typically `missing_fields` or `incorrect_fields` for a found work); otherwise `null`.

## Response hygiene

- Never include internal search tokens (e.g., `turn0search0`) or raw metadata markers in any output field. All text must be clean and human-readable.
- Always cite the URL you used as the authoritative source so the user can verify your finding.
- Never validate from memory — every claim about a reference's correctness must be backed by a fetched URL or search result from this session.
