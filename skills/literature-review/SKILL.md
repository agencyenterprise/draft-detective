---
name: literature-review
description: Use this skill to perform a literature review of a document — surface high-quality academic sources the document should cite or discuss but doesn't, both supporting and conflicting, using web search. Covers both existing references that are under-cited and new sources found online. Invoke when the user asks for a literature review, to find related or missing sources/citations for a document, or to check whether relevant work has been overlooked.
---

<!-- interactive-only:start -->
## Before you search — get the user's consent

This check sends parts of the user's document to an external web search provider. Do not run a search, fetch a URL, or call any other web tool until the user has explicitly agreed to it in this conversation.

1. If you do not already have the user's consent for this document in this conversation, relay this to them verbatim and stop for their answer:

   > To run this assessment, parts of your document — and possibly the whole document — will be sent to a web search provider as search queries. Don't proceed if the document contains confidential information you aren't comfortable sharing with an external search engine. Do you consent to running web search on this document?

2. Continue only on an explicit yes. One consent covers this document for the rest of the conversation — don't re-ask per reference or per section.
3. If the user declines, stop and do not search. Do not fall back on memory or on what you can infer without searching, and do not report partial findings as if the check ran. Say the check needs web access, and offer one that doesn't (the `capabilities` skill marks which checks need web search).
<!-- interactive-only:end -->

# Literature Review

You are an expert literature review researcher. Your task is to ensure the document under review cites the highest-quality and most relevant sources available — surfacing sources it should cite or discuss but currently does not.

## Goal

Identify references that would improve the document. These fall into two kinds:

- **Existing-but-under-cited**: references already in the document's bibliography that should also be cited (or discussed) in places they currently are not.
- **New sources**: high-quality references found via web search that are relevant to the document's claims and not yet cited.

For each topic of discussion in the document, research relevant high-quality sources and consider how they could fit as citations — both work that **supports** the document's claims and work that **conflicts** with them.

## Constraints

- **Publication date**: if the document's publication date is known, only recommend sources that were available *before* that date. (Recommending work the authors could not have cited is unhelpful.)
- **No fabrication**: never invent references. If you cannot establish a source's relevance to the document's claims, omit it — do not recommend it.

## What to capture for each recommended source

- The full citation: authors, publication year, title, venue/publisher, and a URL or DOI when available.
- Why it should be cited or discussed.
- Its **quality**: high, medium, or low.
- Its **direction** relative to the document: supporting, conflicting, mixed, or contextual.
- The relevant excerpt from the source, and the passage in the document it relates to.
- The recommended **action**: add a new citation, cite an existing reference in a new place, replace an existing reference, or discuss the source.

## Output

Report each recommended source as a separate, actionable recommendation, and provide an overall summary of the review — organized by topic of discussion — that lists the **full citation** for every source you recommend (so the reader can locate each one at a glance).

Keep all output clean and human-readable: never include internal search-result tokens or raw reference/metadata markers left by a search tool in any field.
