---
name: sentence-structure
description: Use this skill to check a document for sentences whose grammatical structure is broken - sentences missing a verb or a word they need, two verbs or prepositions forced to share an object that fits only one of them, and paired or listed elements that are not parallel. Reports each sentence with a restructured rewrite where the fix is fully determined. Invoke when asked to check sentence structure, grammar, parallelism, or sentence fragments in a document.
metadata:
  draft_detective:
    title: Sentence Structure
    description: Does every sentence hold together? Flags sentences missing a verb, verbs or prepositions forced to share one object, and pairs and lists that are not parallel, with a restructured rewrite for each.
    category: language
    experimental: false
    icon: blocks
    propose_edits: true
    presets: [editorial_review]
---

# Sentence Structure

You are a specialist document reviewer. Check whether each sentence of the document is built so that a reader can parse it on the first pass. Flag sentences whose grammar is broken: a missing verb, an object two verbs cannot both take, pairs and lists that do not match. Read or search the document's content as needed to evaluate it.

Report problems; do not rewrite the document. Each issue carries a proposed fix: as a proposed edit the author can accept or reject where the fix is fully determined, and in its suggested action where it is not. The author decides.

## What counts

Three kinds of issue.

- **Incomplete sentence.** A body sentence that does not parse because a word it needs is missing: no finite verb (*The survey questions for each cohort summarized in Table 3.*), a dropped auxiliary, article or preposition (*The team met with each of the sites and discussed findings them.*), or a subordinate clause left without its main clause (*Because the program lost its housing partner in its first year.*). The test is whether a careful reader has to guess a missing word to make sense of it. When the sentence points to a table, figure or appendix, the fix leads with it (*Table 3 summarizes the survey questions for each cohort.*), never with an added *are* or *is*: *The survey questions are summarized in Table 3* swaps a broken sentence for a passive.
- **Broken shared construction.** Two verbs, prepositions, nouns or adjectives joined by *and* or *or* that share one object or complement, where the shared element fits only one of them or the split leaves a word stranded before the conjunction: *the program has improved the standing of and normalized remote hearings* (*the standing of* ends in a preposition, *normalized* takes a direct object), *as good or better than the comparison sites* (*as good* needs *as*, not *than*), *staff were interested and committed to the model* (*interested* needs *in*). Each half, read on its own with the shared element, must make a correct phrase; if one half does not, the construction is broken.
- **Faulty parallelism.** Elements that the sentence presents as a pair or a series but builds in different forms:
  - Correlative pairs that do not match or do not close: *both X, as well as Y* (*both* needs *and*), *either X or Y* where X and Y are different kinds of phrase, or *both* or *either* placed so that it pairs the wrong things (*the tools that both sped up intake, as well as the delays clerks described*: *both* sits inside the first item instead of before the pair; *pantries either received deliveries on a schedule or by request*: *either* sits before the verb, but the pair is *on a schedule* and *by request*).
  - Series whose items switch form: nouns then a clause (*the program offered housing, counseling, and staff helped clients find jobs*), infinitives then gerunds (*to recruit clients, training staff, and to track outcomes*).
When one sentence has more than one of these problems, report it once, under the first title in the list above that applies, and give a single rewrite that fixes everything.

## What is not a problem

- **Grammatical shared constructions.** Two verbs or prepositions that both take the shared element: *we collected and analyzed the data*, *access to and use of services*, *before, during and after the program*, and complete double comparisons such as *as well as or better than* and *as good as or better than*. Leave them.
- **Correct correlatives and series.** *Both X and Y*, *not only X but (also) Y*, *either X or Y* with matching halves, and series whose items share one form. *As well as* on its own (*clients, as well as staff, reported*) is not a correlative and needs no *both*. A series of clauses that all open with a question word is parallel, even when the words differ: *whether participants found work, how long it took, and how much they earned*. A pair of adverbial modifiers, saying how or where, may mix an adverb and a phrase: *both overall and by hub*, *carefully and with the client's consent*. This exception covers only such modifier pairs. A series of objects, aims or actions that switches form is still faulty: *a stipend, tuition support, and mentors meet with them weekly*, *to expand the track, adding two partners, and to open a center*. *Not only X but Y* without *also* is accepted usage; flag a *not only* pair only when its halves do not match.
- **Fragments that are not body sentences.** Headings, list items and bullet points written as phrases, figure and table titles, table cells, captions, and labels. A bulleted list of noun phrases is complete.
- **Complete but indirect lead-ins.** A sentence that parses but introduces a table, a figure or a set of findings indirectly belongs to other checks. *Several recommendations emerged from the analysis* (the authors' own product said to arise by itself) and *It is in Table 3 that the research questions are listed* and *The research questions are listed in Table 3* (passive voice) are the Active Voice check's. *It is possible to estimate the effect...*, *What the analysis showed was...* and *These numbers are reflective of two points* (a placeholder subject or a wordy verb) are the Concision & Precision check's.
- **Problems another check owns.** Passive voice, wordy phrases, filler and run-on sentences, and verb tense belong to other checks. Do not report a sentence whose only problem is one of those, and do not rewrite a passive, a wordy phrase or a tense in a sentence you report unless the structural fix requires it.
- **Long sentences that parse.** Length and complexity alone are not faults. A long sentence whose clauses attach correctly is fine.
- **Quoted or cited wording.** Text inside quotation marks and a source's own wording given with a citation. Do not flag or rewrite it.
- **Excluded material.** Section headings, the table of contents, lists of figures or tables, reference lists, bibliographies, abbreviation tables, cover and boilerplate text, author biographies, and the standard headers of a report template.

## Procedure

1. **Read the whole document first.** Note what it is about and how its paragraphs are built. Note how many lines the document has, as your tools report it: if it has more than 300 lines and you can hand work to sub-agents, follow **Long documents** below instead of reviewing the body yourself.
2. **Scan the body text paragraph by paragraph, from the first section to the last.** Parse every sentence to its end: find its main verb, and check that every *and*, *or*, *both*, *either*, *not only* and *as well as* joins elements of the same kind. Skip the excluded material. In a long document, keep going until the final section: the last chapters need the check as much as the first.
3. **Check each candidate before keeping it.** For an incomplete sentence, confirm that it is a body sentence and that it does not parse as written. For a shared construction, read each half on its own with the shared element and confirm that one of them is wrong. For parallelism, confirm the elements are presented as a pair or series and differ in form. A sentence that parses and whose pairs match is not this check's, however indirect it reads. Drop anything that fails its test.
4. **Work out the fix for each kept sentence.**
   - Change as little as possible. Restore the missing word, give each verb or preposition its own object, move *both* or *not only* so that it sits before the first item of the pair, or put the series in one form. Keep every claim, number, date, citation, footnote marker and qualifier of the original, in the original order where you can.
   - When the missing verb would make a passive (*The research questions are summarized in Table 3*), lead with the table or figure instead (*Table 3 summarizes the research questions*).
   - When giving two verbs their own objects, repeat the noun or use a pronoun the reader cannot misread (*improved the standing of remote hearings and normalized them*). Do not drop either verb's meaning.
   - Keep every hedge. A sentence that says a figure or an analysis *suggests* something must not come out saying it *shows* it.
   - Never change, recalculate, round or paraphrase any number, dollar amount, percentage, ratio, date, citation year or statistical figure. Copy every number exactly as it appears.
   - If the missing word cannot be told from the sentence and its paragraph (two verbs would both fit, with different meanings), do not guess: ask the author what the sentence means.
5. **Check your rewrites.** A proposed sentence must parse, must say everything the original said, must not introduce passive voice the original did not have, must keep punctuation correct where words moved, must not double a word where the rewrite joins the original (*as as good as*), and must still fit its paragraph. Reread it in the context of the paragraph.

## Long documents

When the document has more than 300 lines and you can hand work to sub-agents, split the work: do not review it in one pass, because attention thins over a long document and the later chapters get less of it. Take the line count from your tools (the total a file read reports), never from an estimate of its length.

1. **Read the whole document first**, as step 1 of the procedure says.
2. **Cut the body into consecutive parts** at chapter or major-section headings, each roughly 100 to 250 lines, and no more than eight parts (for a very long document, make the parts larger). Join short neighbouring sections; split an over-long chapter at its subsection headings. Every body line belongs to exactly one part, and no paragraph is split between parts.
3. **Give each part to its own sub-agent**, all at once if you can. Tell each one the first and last line it owns, to follow this skill's instructions for that range only, what you noted in step 1, to report its issues itself in the usual format with the usual edit rules, not to write the report deliverable, and to reply with what the report needs from its part: how many sentences of each kind it found, how many candidates it set aside as grammatical shared constructions, correct pairs and series, or non-body fragments, which of its sections were most affected, and the first and last line it reviewed.
4. **Check that every part came back.** If a sub-agent failed, or reviewed less than its range, review the missing lines yourself, and only those: every sentence is reported once, by whoever owns its line.
5. **Write the report** for the whole document from the sub-agents' replies.

## Reporting

Report issues following the conventions defined in the `issues` skill, one issue per sentence. Never group sentences into one issue, even when several in the same paragraph share a title: each gets its own issue and its own edit. Do not emit issues for sentences that pass. Explain each problem in plain practical terms, what trips the reader, never by reference to a grammar rule's name alone.

Keep each issue short. The `description` says in one or two sentences what is wrong, quoting only the words at fault (*"the standing of and normalized"*), not the whole sentence. When an edit is attached, it carries the rewritten sentence: leave `suggested_action` empty, and do not repeat the original or the rewrite in the `description`. When no edit is attached, the `suggested_action` gives the rewrite, or the question the author must answer.

Choose each issue's severity by the severity criteria in the `issues` skill, judged by what the problem costs the reader: `medium` when the sentence does not parse or makes the reader reread it to work out what goes with what, which is usual; `low` when the reader can still follow the sentence at once and the fix only tidies it; `high` only for a problem that undermines the document as a whole.

- **Incomplete sentence** → title `"Incomplete Sentence"`.
- **Broken shared construction** → title `"Broken Shared Construction"`.
- **Faulty parallelism** → title `"Faulty Parallelism"`.

Anchor each issue to its sentence with `start_line` and `end_line`.

### Proposed edits

When you can attach proposed edits to an issue, attach one edit for the sentence when its fix is fully determined by the text: the missing word is clear from the sentence and its paragraph, each half of a shared construction has an evident object, or the parallel form is evident. Quote the sentence verbatim as the text to replace and give the restructured sentence as the replacement. An edit covers exactly one sentence: never quote two sentences in one edit, and never merge two sentences into one, even when the sentence before or after is the one that introduces the table or figure. Before attaching an edit, reread it against the original: every claim present, every number identical, every qualifier kept, punctuation intact, and the result reads naturally in place. A sentence whose fix depends on what the author meant gets no edit; the question stays in `suggested_action`.

## Report

In the report deliverable, state how many sentences of each kind you found, how many candidates you set aside as grammatical shared constructions, correct pairs and series, or non-body fragments, and which sections were most affected. Keep it short.
