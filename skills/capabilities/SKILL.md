---
name: capabilities
description: Use this skill as the entry point when the user gives a generic, unspecified request to use Draft Detective on their document — e.g. "run draft detective", "analyze my document", "review this document", "check my paper", "what can you check?", "what can you do?". It lists everything Draft Detective offers and asks the user what to run. Do NOT use it when the user has already named a specific check or operation (run that skill directly).
---

# Draft Detective — What would you like to run?

The user has asked to use Draft Detective but has **not** specified what to run. Draft Detective offers several capabilities, each implemented as its own skill. Your job here is **only to help them choose** — do not run anything yet, and do not guess on their behalf.

## What to do

1. Present the capabilities below, grouped as shown, each with its short description.
2. Ask the user **what they would like to run**. Make it clear they can pick more than one, or ask for all of them.
3. Wait for their answer. Once they choose, invoke the corresponding skill(s) listed in the "Skill" column. If they ask for several, run them in parallel.
4. If any of their choices is marked **Web search: yes**, get their explicit consent before running it — see "Capabilities that use web search" below.

Keep your message concise and scannable — a short intro line, the lists, and the question.

## Assessments

These review the document and flag issues.

| Assessment | What it checks | Skill | Web search |
|---|---|---|---|
| **Reference Error Checker** | Are your references accurate? Uses web search to confirm each citation exists and that the author, title, publisher, and year match public sources — catching typos and hallucinated references. | `reference-validation` | Yes |
| **Figures & Tables Check** | Are all figures and tables properly titled, consistently numbered, cited in the body text, and do all body-text references resolve to a real figure or table? | `figures-tables-check` | No |
| **Abbreviation Scan** | Are abbreviations and acronyms defined inline at first use, listed in an Abbreviations section, used consistently, and never given conflicting meanings? | `abbreviation-scan` | No |
| **Document Contents** | Does the document include all required sections — About This, Acknowledgements, Methods, Results, Conclusion, References, and an Appendix when one is referenced? | `document-contents` | No |
| **About This** | Does the preface / "About This" section cover the required elements (context, objectives, audience, situating in the literature, contribution, and scope), and does each author biography meet publication requirements (sentence count, position & affiliation, research focus, and highest degree)? | `about-this-preface`, `about-this-authors` | No |
| **Recommendation Check** | Is each recommendation supported by the document's own findings, and can a reader act on it? Flags recommendations with weak, indirect, missing, or contradictory backing, vague recommendations, ones that do not say who should act, and lists of more than three. | `recommendation-check` | No |
| **Internal Inference Validation** | Does the reasoning hold up? Flags logical leaps, unsupported conclusions, and arguments where the evidence doesn't support the claim. | `inference-validation` | No |
| **Claim Reference Validation** | Does each cited source actually back the claim it's attached to? Judges every citation as supported, partially supported, contradicted, unsupported, or unverifiable against the cited source. (Needs the full text of the cited sources: provide them, or they can be fetched with web search.) | `citation-support` | Only to fetch missing sources |
| **Advocacy & Tone** | Does the document use neutral, objective language? Flags trigger words (certainty language without evidence), advocacy language (unsupported recommendations or opinion framing), and subjective tone. (Alpha.) | `advocacy-tone` | No |
| **Reviewer 2** | A rigorous simulated peer review — summary, strengths, weaknesses, and prioritized next steps — plus a separate devil's-advocate rebuttal. (Alpha.) | `reviewer-2` | No |
| **Methodological Alignment** | Does your methodology match standard practice in the field? Uses web search to characterize the field baseline, then compares your approach — similarities, differences, missing components, rigor, and suggested improvements. | `methodology-comparison` | Yes |
| **Reproducibility Check** | Could someone reproduce your results from the document alone? Extracts the main results and classifies each by how reproducible it is. (Alpha.) | `reproducibility-check` | No |

## Peer review response

This helps you respond to peer reviewers rather than analyzing a single document. It works from a draft (and optionally a revised draft) plus one or more reviewer memos.

| Capability | What it does | Skill | Web search |
|---|---|---|---|
| **Review Assistant** | Generate the artifacts of a peer-review response cycle: a revision-planning summary, one reviewer response memo per reviewer, and a consolidated reviewer coverage report for a QA manager. Reproduces each reviewer memo verbatim and states how the revision addressed every point. | `review-assistant` | No |

## Tools

These operate on the document rather than flagging issues.

| Tool | What it does | Skill | Web search |
|---|---|---|---|
| **Download References** | Search the web for a reference and download its full original content (PDF/Markdown), verifying the match. Reports found / found-but-inaccessible / not-found. | `reference-download` | Yes |
| **Extract Methodology** | Extract a structured, reproducible description of the paper's methodology, and classify how reproducible it is. | `methodology-extraction` | No |
| **Extract References** | Find and list all bibliographic references from the document's reference/bibliography section. | `reference-extraction` | No |
| **Extract Abbreviations** | Find and catalogue every abbreviation/acronym occurrence — with its inline definition, occurrence count, location, Abbreviations-section entry, and exempt-class status. | `abbreviation-extraction` | No |

## Capabilities that use web search

The capabilities marked **Web search: yes** send parts of the document — and possibly the whole document — to an external web search provider as search queries. That is unavoidable for what they do: they check the draft against the outside world rather than against itself.

Because the document leaves the conversation, these need the user's explicit consent before they run. Each of those skills opens with the consent step and the exact wording to relay; follow it. Do not search first and ask afterwards, and do not run one of these because it was part of an "everything" or "all of them" request — an "all of them" ask still needs one consent for the web-search ones.

If the user declines, run the checks marked **No** and tell them which ones you skipped and why.

## Notes

- If the user's request actually does name a specific capability (e.g. "check my references", "extract the bibliography", "download this citation"), skip the menu and invoke that skill directly instead of using this one.
- Most capabilities operate on the document the user has provided or uploaded; if none is available yet, ask them to share it.
