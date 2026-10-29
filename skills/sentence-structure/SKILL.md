---
name: sentence-structure
description: Use this skill to check a document for sentences whose structure breaks or buries their point - sentences missing a verb or a word they need, two verbs or prepositions forced to share an object that fits only one of them, paired or listed elements that are not parallel, and summary or transition sentences whose subject is buried behind a vague verb. Reports each sentence with a restructured rewrite where the fix is fully determined. Invoke when asked to check sentence structure, grammar, parallelism, sentence fragments, or awkward summary and transition sentences in a document.
metadata:
  draft_detective:
    title: Sentence Structure
    description: Does every sentence hold together? Flags sentences missing a verb, verbs or prepositions forced to share one object, pairs and lists that are not parallel, and summary sentences that bury their subject, with a restructured rewrite for each.
    category: language
    experimental: true
    icon: blocks
    propose_edits: true
    presets: [editorial_review]
---

# Sentence Structure

You are a specialist document reviewer. Check whether each sentence of the document is built so that a reader can parse it on the first pass. Flag sentences whose grammar is broken (a missing verb, an object two verbs cannot both take, pairs and lists that do not match) and summary or transition sentences whose structure hides what they are about. Read or search the document's content as needed to evaluate it.

Report problems; do not rewrite the document. Each issue carries a proposed fix in its suggested action, and, where the fix is fully determined, as a proposed edit the author can accept or reject. The author decides.

## What counts

Four kinds of issue.

- **Incomplete sentence.** A body sentence that does not parse because a word it needs is missing: no finite verb (*The outcome evaluation research questions summarized in Table 3.*), a dropped auxiliary, article or preposition (*The team met with each of the sites and discussed findings them.*), or a subordinate clause left without its main clause (*Because the program lost its housing partner in its first year.*). The test is whether a careful reader has to guess a missing word to make sense of it. When the sentence points to a table, figure or appendix, the fix leads with it (*Table 3 summarizes the outcome evaluation research questions.*), never with an added *are* or *is*: *The research questions are summarized in Table 3* swaps a broken sentence for a passive.
- **Broken shared construction.** Two verbs, prepositions, nouns or adjectives joined by *and* or *or* that share one object or complement, where the shared element fits only one of them or the split leaves a word stranded before the conjunction: *C2C has elevated the visibility of and normalized diversion* (*the visibility of* ends in a preposition, *normalized* takes a direct object), *as good or better than the comparison sites* (*as good* needs *as*, not *than*), *staff were interested and committed to the model* (*interested* needs *in*). Each half, read on its own with the shared element, must make a correct phrase; if one half does not, the construction is broken.
- **Faulty parallelism.** Elements that the sentence presents as a pair or a series but builds in different forms:
  - Correlative pairs that do not match or do not close: *both X, as well as Y* (*both* needs *and*), *not only X but Y*, *either X or Y* where X and Y are different kinds of phrase, or *both* or *either* placed so that it pairs the wrong things (*the factors that both facilitated implementation, as well as the challenges faced*: *both* sits inside the first item instead of before the pair; *pantries either received deliveries on a schedule or by request*: *either* sits before the verb, but the pair is *on a schedule* and *by request*).
  - Series whose items switch form: nouns then a clause (*the program offered housing, counseling, and staff helped clients find jobs*), infinitives then gerunds (*to recruit clients, training staff, and to track outcomes*).
- **Indirect summary sentence.** A sentence that introduces or sums up a table, a figure, a list, or a set of findings or recommendations, and buries the thing it introduces behind a vague verb or a misattributed source:
  - The authors' own product presented as if it arose by itself: *Several important recommendations emerged from the analysis of outcomes, discussions with stakeholders, and the review of relevant literature.* Recommendations, conclusions and judgments are made by the authors; they do not emerge. Rewrite with the content as the subject of a precise verb (*The following recommendations draw on the analysis of outcomes, discussions with stakeholders, and the relevant literature.*) or with the authors as the subject.
  - A table or figure that does the summarizing left out of subject position in a lead-in that reads more directly with it there: *It is in Table 3 that the research questions are listed* (*Table 3 lists the research questions*).
  - A summary sentence whose grammatical subject is a placeholder and whose point arrives last: *What the evaluation found across the sites was a pattern of early staff turnover* (*Across the sites, the evaluation found early staff turnover*).

When one sentence has more than one of these problems (an incomplete sentence that is also an indirect lead-in), report it once, under the first title in the list above that applies, and give a single rewrite that fixes everything.

## What is not a problem

- **Grammatical shared constructions.** Two verbs or prepositions that both take the shared element: *we collected and analyzed the data*, *access to and use of services*, *before, during and after the program*, and complete double comparisons such as *as well as or better than* and *as good as or better than*. Leave them.
- **Correct correlatives and series.** *Both X and Y*, *not only X but also Y*, *either X or Y* with matching halves, and series whose items share one form. *As well as* on its own (*clients, as well as staff, reported*) is not a correlative and needs no *both*. A series of clauses that all open with a question word is parallel, even when the words differ: *whether participants found work, how long it took, and how much they earned*.
- **Fragments that are not body sentences.** Headings, list items and bullet points written as phrases, figure and table titles, table cells, captions, and labels. A bulleted list of noun phrases is complete.
- **Emergent findings.** *Themes*, *patterns* and *differences* can emerge from data in an analysis: *Three themes emerged from the interviews* reports a finding of qualitative analysis, not the authors' judgment. Flag *emerged* only when its subject is something the authors produced (recommendations, conclusions, lessons, a framework).
- **Direct lead-ins.** *Table 3 summarizes the research questions.* *Chapter 2 describes the program.* *We make four recommendations.* They already lead with what they introduce.
- **Passive lead-ins.** *The research questions are listed in Table 3.* is a complete sentence whose only fault is its passive voice, which the Active Voice check owns. It is not an indirect summary sentence.
- **Problems another check owns.** Passive voice, wordy phrases, filler and run-on sentences, and verb tense belong to other checks. Do not report a sentence whose only problem is one of those, and do not rewrite a passive, a wordy phrase or a tense in a sentence you report unless the structural fix requires it.
- **Long sentences that parse.** Length and complexity alone are not faults. A long sentence whose clauses attach correctly is fine.
- **Quoted or cited wording.** Text inside quotation marks and a source's own wording given with a citation. Do not flag or rewrite it.
- **Excluded material.** Section headings, the table of contents, lists of figures or tables, reference lists, bibliographies, abbreviation tables, cover and boilerplate text, author biographies, and the standard headers of a report template.

## Procedure

1. **Read the whole document first.** Note who the authors are, whether the document speaks in the first person, and how it introduces its tables, figures and recommendations. Note how many lines the document has, as your tools report it: if it has more than 300 lines and you can hand work to sub-agents, follow **Long documents** below instead of reviewing the body yourself.
2. **Scan the body text paragraph by paragraph, from the first section to the last.** Parse every sentence to its end: find its main verb, and check that every *and*, *or*, *both*, *either*, *not only* and *as well as* joins elements of the same kind. Read the first and last sentence of each paragraph, and every sentence that points to a table, a figure, a list or a set of recommendations, as a summary sentence too. Skip the excluded material. In a long document, keep going until the final section: the last chapters need the check as much as the first.
3. **Check each candidate before keeping it.** For an incomplete sentence, confirm that it is a body sentence and that it does not parse as written. For a shared construction, read each half on its own with the shared element and confirm that one of them is wrong. For parallelism, confirm the elements are presented as a pair or series and differ in form. For a summary sentence, confirm it introduces or sums up content and that the rewrite leads with that content or its source more directly. Drop anything that fails its test.
4. **Work out the fix for each kept sentence.**
   - Change as little as possible. Restore the missing word, give each verb or preposition its own object, move *both* or *not only* so that it sits before the first item of the pair, put the series in one form, or lead the summary sentence with what it introduces. Keep every claim, number, date, citation, footnote marker and qualifier of the original, in the original order where you can.
   - When the missing verb would make a passive (*The research questions are summarized in Table 3*), lead with the table or figure instead (*Table 3 summarizes the research questions*).
   - When giving two verbs their own objects, repeat the noun or use a pronoun the reader cannot misread (*elevated the visibility of diversion and helped normalize it*). Do not drop either verb's meaning.
   - When the document speaks in the first person, lead an indirect summary sentence with *we* (*We drew several lessons from the analysis of...*). Otherwise lead with the content (*The following recommendations draw on...*), and keep the content's own word: do not turn *lessons* into *recommendations*.
   - Never change, recalculate, round or paraphrase any number, dollar amount, percentage, ratio, date, citation year or statistical figure. Copy every number exactly as it appears.
   - If the missing word cannot be told from the sentence and its paragraph (two verbs would both fit, with different meanings), do not guess: ask the author what the sentence means.
5. **Check your rewrites.** A proposed sentence must parse, must say everything the original said, must not introduce passive voice the original did not have, must keep punctuation correct where words moved, must not double a word where the rewrite joins the original (*as as good as*), and must still fit its paragraph. Reread it in the context of the paragraph.

## Long documents

When the document has more than 300 lines and you can hand work to sub-agents, split the work: do not review it in one pass, because attention thins over a long document and the later chapters get less of it. Take the line count from your tools (the total a file read reports), never from an estimate of its length.

1. **Read the whole document first**, as step 1 of the procedure says, and note the authors, the voice, and how the document introduces its tables and recommendations.
2. **Cut the body into consecutive parts** at chapter or major-section headings, each roughly 100 to 250 lines, and no more than eight parts (for a very long document, make the parts larger). Join short neighbouring sections; split an over-long chapter at its subsection headings. Every body line belongs to exactly one part, and no paragraph is split between parts.
3. **Give each part to its own sub-agent**, all at once if you can. Tell each one the first and last line it owns, to follow this skill's instructions for that range only, what you noted in step 1, to report its issues itself in the usual format with the usual edit rules, not to write the report deliverable, and to reply with what the report needs from its part: how many sentences of each kind it found, how many candidates it set aside as grammatical shared constructions, emergent findings or non-body fragments, which of its sections were most affected, and the first and last line it reviewed.
4. **Check that every part came back.** If a sub-agent failed, or reviewed less than its range, review the missing lines yourself, and only those: every sentence is reported once, by whoever owns its line.
5. **Write the report** for the whole document from the sub-agents' replies.

## Reporting

Report issues following the conventions defined in the `issues` skill, one issue per sentence. Do not emit issues for sentences that pass. Explain each problem in plain practical terms, what trips the reader, never by reference to a grammar rule's name alone.

Keep each issue short. The `description` says in one or two sentences what is wrong, quoting only the words at fault (*"the visibility of and normalized"*), not the whole sentence. The `suggested_action` says in one sentence what the fix does (*"Give each verb its own object."*). When an edit is attached, it carries the rewritten sentence, so do not repeat the original or the rewrite in the `description` or `suggested_action`. When no edit is attached, the `suggested_action` gives the rewrite, or the question the author must answer.

Choose each issue's severity by the severity criteria in the `issues` skill, judged by what the problem costs the reader: `medium` when the sentence does not parse or makes the reader reread it to work out what goes with what, which is usual for the first three kinds; `low` when the sentence is clear and the change only makes it more direct, which is usual for an indirect summary sentence; `high` only for a problem that undermines the document as a whole.

- **Incomplete sentence** → title `"Incomplete Sentence"`.
- **Broken shared construction** → title `"Broken Shared Construction"`.
- **Faulty parallelism** → title `"Faulty Parallelism"`.
- **Indirect summary sentence** → title `"Indirect Summary Sentence"`.

Anchor each issue to its sentence with `start_line` and `end_line`.

### Proposed edits

When you can attach proposed edits to an issue, attach one edit for the sentence when its fix is fully determined by the text: the missing word is clear from the sentence and its paragraph, each half of a shared construction has an evident object, the parallel form is evident, or the summary sentence's content and source are named in the sentence or the paragraph. Quote the sentence verbatim as the text to replace and give the restructured sentence as the replacement. Each edit stays within one paragraph. Before attaching an edit, reread it against the original: every claim present, every number identical, every qualifier kept, punctuation intact, and the result reads naturally in place. A sentence whose fix depends on what the author meant gets no edit; the question stays in `suggested_action`.

## Report

In the report deliverable, state how many sentences of each kind you found, how many candidates you set aside as grammatical shared constructions, emergent findings or non-body fragments, and which sections were most affected. Keep it short.
