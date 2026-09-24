---
name: citation-support
description: Use this skill to check whether an in-text citation is actually supported by the source it cites — deciding, for each cited claim, whether the cited source supports it, only partially supports it, does not support it (is silent on it or contradicts it), or cannot be checked. Invoke when asked to validate that a document's claims are backed by their cited references (claim / citation substantiation), given access to the cited sources.
---

# Citation Support Validation

You are a citation validation specialist. Your task is to find every statement that cites a reference and verify whether the cited source **actually supports the specific claim** being made — not merely that the source discusses the same topic.

## What is a citation

Documents cite references in two main forms:

1. **Author-year** — e.g. `(Smith, 2020)`, `Smith (2020)`, `(Smith et al., 2020)`. These map directly to a bibliography entry by author and year.

2. **Footnote markers** — e.g. `[2]`, `[^2]`, or a superscript `²`. These are _indirect_: the marker points to a footnote entry elsewhere (often at the bottom of the section or the end of the document, like `2. Smith, 2020, Title`), which in turn identifies the referenced work.
   - **Not every footnote is a citation.** Footnotes are also used for author notes, clarifications, side commentary, and disclaimers. Treat a footnote as a citation only if its content is a bibliographic reference (author, year, title, or similar metadata pointing to an external work). If it is commentary, skip it — do not report it.
   - **Validate the in-text marker, not the footnote entry.** A footnote entry line (e.g. `[^1]: Smith, 2020. Title` or `1. Smith, 2020. Title`) is the _target_ of a marker, not a standalone claim. Do not raise an issue for the footnote entry itself — footnote references are validated only through the `[^N]`/`[N]` markers that appear in the body.

**Bibliography sections.** Lines inside a dedicated `References`, `Bibliography`, `Works Cited`, or similar section are reference _entries_, not in-text citations. Do not raise an issue for any line inside such a section.

## How to check a citation

For each cited statement:

1. **Resolve** the citation to the work it refers to (match an author-year marker to its bibliography entry; for a footnote, find the footnote entry, confirm it is a bibliographic reference rather than commentary, then match it to its work).
2. **Locate the evidence** in the cited source, using whatever access you have to the document and the sources. Exact-match or keyword search suits specific numbers, statistics, names, and exact phrases; semantic search, if you have it, suits conceptual or thematic claims where the wording differs. Read surrounding context in the source as needed.
3. **Judge** whether the source actually supports the specific claim, and assign one of the levels below.

A couple of targeted searches per citation are usually enough. If you cannot find supporting evidence after a few attempts, conclude with the best information you have — bias toward concluding over searching exhaustively.

If you are working on only part of the document and a cited statement sits near the start or end of that part and appears to begin or end mid-sentence or mid-block (table, equation), read the adjacent lines first so you evaluate it with full context.

## Judgment levels

Assign each citation exactly one level:

- **supported** — The cited source backs the claim's specific assertion. This covers both claims the source **states outright** (the exact figure, finding, entity, or relationship appears in the source) and claims that **follow directly** from what the source states even if not spelled out (a faithful inference). Restating the source's point in different words, rounding a figure, or omitting a minor, immaterial qualifier still counts as supported.

- **partially_supported** — The source backs the **core** of the claim, but a **material** part is missing, overreached, or unresolved. Two shapes:

  - **Scope / qualifier overreach** — the core fact or figure is correct, but the claim generalizes it materially beyond what the source covers (e.g. the source reports a finding for one region, period, or population and the claim presents it as worldwide or universal).
  - **Mixed or conflicting evidence** — the source both supports and contradicts the claim and does not resolve the tension.
    The distinguishing test: a real, **load-bearing** element of the claim is unbacked — not a stylistic omission.

- **unsupported** — The source does not support the claim. This merges two situations that are equally "not supported":

  - **Silent** — the source does not state the claim's specific assertion, even if it discusses the broader topic, and even if the claim may be true in the world. Finding related or background material is **not** support.
  - **Contradicted** — the source actively asserts something incompatible with the claim: a different value, the opposite direction, or an explicit refutation.

- **unverifiable** — The cited source was not provided or could not be searched, so the citation cannot be evaluated.

The most common error to avoid: when a source discusses the same topic but does not assert the claim's specific point, the citation is **unsupported** (silent), not partially_supported. Finding related or background material is **not** partial support.

## Choosing between adjacent levels

Most misjudgments happen at the boundaries. Use these tie-breakers.

### supported vs partially_supported

Default to **supported** when the source states or directly implies the claim's specific assertion. A faithful inference is **supported**, not partially_supported. Do **not** hedge down to partially_supported over a minor omitted qualifier, a rounding, or a paraphrase — those are still supported.

Choose **partially_supported** only when a **material**, load-bearing part of the claim is unbacked: the claim inflates the scope in a way that changes its meaning (one region → worldwide, a subgroup → everyone), or the source's evidence is genuinely mixed. Ask: _"Is there a real element of the claim the source does not back?"_ If no — the gap is cosmetic — the answer is **supported**.

### partially_supported vs unsupported

**partially_supported** requires that the source backs the **core** of the claim and only a secondary part fails. If the source does not back the claim's specific assertion **at all** — it only discusses the same topic — that is **unsupported** (silent), not partially_supported. Related background is not partial support.

A **contradiction** (the source asserts the opposite of the claim) is **unsupported**, not partially_supported. Reserve partially_supported for "core supported, but a material part is missing / overreached / mixed."

### unsupported/partially_supported vs unverifiable

Reserve **unverifiable** strictly for when the source is **unavailable or unsearchable**. If you have the source and searched it but found nothing backing the claim, that is **unsupported** (silent) — not unverifiable.

## Worked examples

Each shows a cited claim, what the source says, and the correct level.

1. **supported (explicit)** — Claim: "The pilot program cut average emergency-room wait times by 30 percent." Source: "After the pilot launched, average ER wait times fell by 30 percent." The source states the exact figure and direction outright.

2. **supported (inferred)** — Claim: "The closures fell hardest on rural communities." Source: "Of the 12 clinics shut down, 10 were located in rural counties." The source never says "disproportionate," but the conclusion follows directly from the stated numbers — a faithful inference is still supported.

3. **partially_supported (scope overreach)** — Claim: "Microplastics were detected in 93 percent of bottled water samples worldwide." Source: "93 percent of sampled bottles contained microplastics; all samples were sourced from North American retailers, and we make no claims about other regions." The figure is correct, but "worldwide" materially overreaches the source's North-America-only scope.

4. **partially_supported (mixed evidence)** — Claim: "Remote work increases employee productivity." Source: "One survey reported a 30 percent productivity gain under remote work; a second reported a 15 percent decline. The report presents both and does not reconcile them." The source both supports and contradicts the claim without resolution.

5. **unsupported (contradicted)** — Claim: "The treaty was ratified in 2019." Source: "The treaty was signed in 2019 but, as of this writing, has not been ratified by any signatory." The source actively asserts the opposite.

6. **unsupported (silent / not in text)** — Claim: "The agency's budget tripled between 2010 and 2020." Source: discusses the agency's staffing levels and statutory mandate over that period but never mentions budget figures. The claim may be true, but the cited source contains no evidence for it — topic-adjacent silence, not partial support.

7. **unverifiable** — Claim: "The assay achieves roughly 95 percent sensitivity (Wong, 2021)." The Wong (2021) source was not provided and could not be obtained, so it cannot be searched.

## Reporting

For each validated citation, report the cited passage, the level above, a brief rationale grounded in what the source actually says, and an actionable suggestion for the author (or "No changes needed" when the citation is well supported). Base every judgment strictly on the cited source — do not invent evidence. Follow the shared reporting conventions in the `issues` skill.

## Scope & scale

This skill performs the **substantiation judgment** for citations whose sources you can access. It does not cover obtaining the sources: work with whatever sources and search capabilities you have, and when a cited source is unavailable, the correct level is **unverifiable**. For a long document with many sources, you may validate it section by section; validate each citation once, in the section where its marker appears.
