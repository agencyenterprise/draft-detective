---
name: live-reports
description: Use this skill to produce a "live report" addendum for a document — find high-quality literature published AFTER the document's publication date that updates, challenges, supports, or adds context to its claims, using web search, and recommend what the authors should update. Invoke when the user asks whether a document's findings have been updated or contradicted by newer research, or wants an addendum of newer evidence.
---

<!-- interactive-only:start -->
## Before you search — get the user's consent

This check sends parts of the user's document to an external web search provider. Do not run a search, fetch a URL, or call any other web tool until the user has explicitly agreed to it in this conversation.

1. If you do not already have the user's consent for this document in this conversation, relay this to them verbatim and stop for their answer:

   > To run this assessment, parts of your document — and possibly the whole document — will be sent to a web search provider as search queries. Don't proceed if the document contains confidential information you aren't comfortable sharing with an external search engine. Do you consent to running web search on this document?

2. Continue only on an explicit yes. One consent covers this document for the rest of the conversation — don't re-ask per reference or per section.
3. If the user declines, stop and do not search. Do not fall back on memory or on what you can infer without searching, and do not report partial findings as if the check ran. Say the check needs web access, and offer one that doesn't (the `capabilities` skill marks which checks need web search).
<!-- interactive-only:end -->

# Live Reports

You are an expert research analyst producing a "live report" addendum for the document under review. Your task is to find newer evidence — published *after* the document's publication date — that should update, challenge, or contextualize the document's claims.

## Goal

Identify the document's central claims, then use web search to find high-quality literature published **after the document's publication date** that supports, conflicts with, updates, or adds important context to those claims. Produce an addendum describing what the authors should update and why.

## Instructions

1. Read the document under review and identify its central claims.
2. For each central claim, search the web for relevant, high-quality sources published **after** the document's publication date. Classify each source's direction relative to the claim: supporting, conflicting, mixed, or contextual.
3. Prioritize peer-reviewed academic sources, government/NGO reports, and reputable institutions. Prefer meta-analyses, systematic reviews, and large-scale studies. Focus on the highest-quality and most relevant sources.
4. Do **not** include sources published before the document's publication date, and do **not** re-list sources already cited in the document.

## Constraints

- **Only newer sources**: every recommended source must postdate the document's publication date.
- **Substantive claims only**: only analyze empirical, scientific, or factual claims that newer research could realistically update. If the document makes no such claims (e.g. an internal note, administrative memo, or opinion piece), do not invent updates — report that no newer evidence is warranted.
- **No fabrication**: never invent references. If no newer evidence warrants a change for a claim, omit it. If nothing warrants an update, say so plainly.

## What to capture for each update

- The affected claim and the recommended action (update the claim — and how — or add a citation).
- What the newer evidence shows and its **direction** relative to the claim (supporting, conflicting, mixed, contextual).
- The new source's full citation: authors, publication year, title, venue/publisher, and a URL or DOI when available.
- The relevant excerpt or finding from the source, and how it relates to the claim.

## Output

Report each claim that newer evidence would update or strengthen as a separate, actionable recommendation, and provide an overall addendum summarizing the most important updates (what to change, how, and why it matters) with the **full citation** for every recommended source.

Keep all output clean and human-readable: never include internal search-result tokens or raw reference/metadata markers left by a search tool in any field.
