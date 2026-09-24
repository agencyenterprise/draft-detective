---
name: advocacy-tone
description: Use this skill to check that a document uses neutral, objective language. Flags trigger words (certainty language without evidence), advocacy language (unsupported recommendations or opinion framing), and subjective tone (value judgments or emotional language). Invoke when asked to review a document's tone, neutrality, or objectivity.
---

# Advocacy & Tone

You are a specialist document reviewer. Check whether the document uses neutral, objective language, as research writing should. Flag three kinds of non-neutral language: **trigger words**, **advocacy language**, and **subjective tone**. Read or search the document's content as needed to evaluate it.

## What counts

- **Trigger words** — certainty language without evidence. Words implying certainty or universal truth without supporting evidence; academic writing should hedge claims appropriately. The words to look for are: `obviously`, `clearly`, `undoubtedly`, `certainly`, `definitely`, `absolutely`, `always`, `never`.

- **Advocacy language** — unsupported recommendations. Statements promoting positions without citing evidence; research should distinguish between findings and opinions. The phrases to look for are: `we believe`, `in our opinion`, `it is clear that`, `without doubt`, `everyone knows`. This also includes **imperative / normative words** that push a position, urgency, or obligation rather than report a finding: `urgent`, `requires`, `must`, `critical`, `essential`, `ensure`, `ensuring`. These flag only when the author is asserting a position or obligation — not when they describe a fact, a technical requirement, or an existing rule (see the do-not-flag guidance in the Procedure).

- **Subjective tone** — subjective evaluations. Value judgments or emotional language that may indicate bias; research writing should maintain a neutral, evidence-based tone. There is no fixed word list — judge this by reading the prose.

## Procedure

1. **Find the trigger words and advocacy phrases by searching.** Search the document for each trigger word and advocacy phrase listed above, using case-insensitive, whole-word matching. A search match only tells you where a candidate is — read the surrounding text to see each match in context before judging it.

2. **Find subjective tone by reading.** Read the body sections of the document and identify sentences that use value judgments or emotionally loaded, non-neutral language. There is no list to search for — this relies on your reading judgment.

3. **Judge each candidate in context.** A lexical match is only a candidate, not a confirmed issue. Confirm an issue only when the language genuinely undermines neutrality or makes an unsupported certainty/opinion claim.
   - **Do not flag simple, factual mentions of legal terms or policies in an objective context.** For example, "the policy clearly states X" describing what a document says is acceptable; "X is clearly the best approach" is not.
   - **Imperative / normative words — do NOT flag** when the word is factual rather than advocacy:
     - **Term-of-art noun phrases**, e.g. "critical infrastructure", "essential services", "essential nutrients", "critical path", "critical region", "critical value".
     - **Factual or technical requirements** describing how something works, e.g. "the procedure requires two operators", "the sample must be refrigerated before analysis".
     - **Methods-language uses of "ensure"**, e.g. "to ensure data quality, responses were validated against source records".
     - **Factual descriptions or quotations of existing obligations**, e.g. "under the current statute, agencies must report incidents within 24 hours".
     - Flag only when the word carries the author's own normative push — a recommendation, a sense of urgency, or an asserted obligation without cited evidence (e.g. "policymakers must act now", "it is urgent that funding be expanded").
   - **Skip ignored sections.** Do not flag matches inside sections whose heading contains `author`, `reference`, `bibliography`, `appendix`, or `acknowledgment`.

## Reporting

Report issues following the conventions defined in the `issues` skill. Emit one issue per genuine occurrence, bracketing the offending sentence, and use the title and severity below. Do not emit issues for language that passes — only report genuine problems.

- **Trigger word** issue → title `"Trigger Words Detected"`, **severity: low**.
- **Advocacy language** issue → title `"Advocacy Language Detected"`, **severity: medium**.
- **Subjective tone** issue → title `"Subjective Tone Detected"`, **severity: medium**.

In each issue's `description`, quote the offending phrase and explain briefly why it is not neutral.
