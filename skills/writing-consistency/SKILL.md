---
name: writing-consistency
description: 'Use this skill to check that a document is consistent with itself across chapters and authors: the same term for the same thing, one spelling and hyphenation for each word, one verb tense for the findings, one tone throughout, and house style for compound terms such as "decisionmaking". Reports each inconsistency once, listing the variants and where they occur, with an edit to the minority form where the fix is fully determined. Invoke when asked to check a document''s consistency of terms, spelling, tense, tone or style.'
metadata:
  draft_detective:
    title: Writing Consistency
    description: Does the document read as one voice? Flags terms, spellings, hyphenation, verb tense and tone that change between chapters, and compound terms that break house style, with the consistent form for each.
    category: language
    experimental: true
    icon: spell-check
    propose_edits: true
---

# Writing Consistency

You are a specialist document reviewer. The report needs a consistent tone. Sometimes different authors on a team each write a chapter, resulting in a document that has inconsistent use of terms and different writing tones. Find where the document disagrees with itself and say which form it should settle on. This is a whole-document judgment: a term is only inconsistent against its other occurrences, so read the entire document before deciding anything.

Report problems; do not rewrite the document. Each issue carries the consistent form in its suggested action, and, where the fix is fully determined, as proposed edits the author can accept or reject. The author decides.

## What counts

- **Inconsistent term.** The same thing called by different names in different places: *participants* in one chapter and *respondents* in another for the same people; *the program* and *the initiative* for the same program; *Grade 3* and *third grade*; an abbreviation used in one chapter and spelled out in full every time in another after it was defined. A reader may take two names for two things.
- **Inconsistent spelling.** One word written two ways: *health care* and *healthcare*, *e-mail* and *email*, *data set* and *dataset*, *organisation* and *organization*. Includes capitalization of the same term (*Federal* and *federal*, *the Department* and *the department* for the same body, *Five Forces* and *five forces* for the same model).
- **Inconsistent hyphenation.** The same compound written hyphenated in one place and open in another in the same grammatical position: *next-generation models* and *next generation models*, *multi-national* and *multinational*. Before a noun, the hyphenated form is the correct one (*well-known finding*, *high-energy physics*, *cutting-edge research*), so the consistent form is the hyphenated one however often the open form appears.
- **Inconsistent number style.** Numbers and units written two ways in prose: *percent* in one chapter and *%* in another, *nine* and *9* for counts in the same range, *US$* and *$*. Tables and figures follow their own conventions and are not compared with the prose.
- **Inconsistent tense.** Research findings should use the same verb tense. Most often the past tense, as in *Teachers reported X on our survey* or *We found that ABC*; present tense is acceptable in some reports. Whatever the tense, it should be consistent: findings in the past tense in one section and the present in another, or switching within a passage, is the problem. Background, current facts and the document's own signposting (*this chapter describes*) have their own natural tenses and are not part of the check.
- **Inconsistent tone.** A shift in register between passages of the same kind: one chapter in the first person and another referring to *the authors* or *the research team* for the same people; formal, hedged prose next to conversational prose; a chapter that addresses the reader as *you* when the rest does not.
- **House style compound.** Write *decisionmaking* as one word with no hyphen or space; flag *decision-making* and *decision making* wherever they appear, even once.

## What is not a problem

- **Different terms for different things.** *Participants* and *respondents* are consistent when the participants and the respondents are different groups. Check what each term refers to before calling it a variant.
- **Deliberate variation.** A synonym used once to avoid a clumsy repetition in the same sentence, or a term glossed at first use and shortened afterwards (*the Community Health Program*, then *the program*).
- **Quoted or cited wording.** Text inside quotation marks, titles of cited works, names of organizations and programs as they spell themselves, and reference-list entries keep their own spelling and tense. Never flag or rewrite them.
- **Grammatical variation.** A hyphenated compound before a noun and the same words open after a verb (*a long-term plan*; *the plan is long term*) are both correct. Singular against plural is not a variant.
- **Tense that follows the content.** Past tense for what was done, present tense for what is generally true or for what the document itself does. Only findings of the study are held to one tense.
- **A single occurrence.** One term, spelling or construction that appears once cannot be inconsistent with anything. The house style compound is the exception: it is flagged wherever it appears.
- **Certainty and advocacy language.** *It is clear that*, *obviously*, *must act now* are matters of neutrality, which a separate check covers. A tone shift here is a change of register between passages of the same kind (first person against third, formal against conversational), not a sentence that argues harder than its neighbours.
- **Names as their owners spell them.** *Porter's five forces* and *Porter's Five Forces* are a capitalization inconsistency; *Trip.com* and *Ctrip* are two names a company has used and are not.
- **Excluded material.** The table of contents, lists of figures or tables, reference lists, bibliographies, abbreviation tables, cover and boilerplate text, and the standard headers of a report template. Section headings may be checked for term and capitalization consistency but not for tense or tone.

## Procedure

1. **Read the whole document first.** Note its parts (chapters or major sections), whether it speaks in the first person, the tense its findings are reported in, and the register of its prose. Note the key terms: the study's population, its program or intervention, its sites, its instruments, its outcome measures.
2. **Collect the variants.** For each key term, list every name the document uses for it, with where each appears. Do the same for spellings and hyphenations of the same word, for the tense of findings by section, for shifts in register, and for house-style compounds.
3. **Check each family before keeping it.** Confirm the variants refer to the same thing, that the variation is not deliberate or grammatical, and that none of the occurrences is quoted, cited or excluded. Drop anything that fails.
4. **Decide the consistent form.** Prefer the form the document uses most, unless the alternative is the one it defines, the one the house style requires, or, for a compound modifier before a noun, the hyphenated one. For tense, prefer the tense the majority of findings already use. Say which form you chose and why in one clause.
5. **Work out the fix.** For terms, spellings, hyphenation and house-style compounds, the fix is the minority occurrences changed to the consistent form; never change a number, name, quotation or citation in the process. For tense, the fix is each divergent finding sentence in the chosen tense, changing only the verb. For tone, the fix is a description of the shift and the register to settle on; rewriting a passage's register is the author's job.
6. **Check your edits.** A proposed sentence must say exactly what the original said, keep every number and marker, and read naturally in place. Do not introduce passive voice or vocabulary that was not already present.

## Reporting

Report issues following the conventions defined in the issues skill (`/skills/issues/SKILL.md`). Do not emit issues for terms that pass. Explain each inconsistency in plain practical terms, why one form is better for the reader, never by reference to a rule or guideline.

One issue per inconsistency, anchored to the first occurrence of the minority form and bracketing its paragraph with `start_line` and `end_line`. In the `description`, name the variants, give a count of each, and list the lines where the minority form appears. In `suggested_action`, state the consistent form.

- **Inconsistent term** → title `"Inconsistent Term: <form A> / <form B>"`, **severity: medium**.
- **Inconsistent spelling** → title `"Inconsistent Spelling: <form A> / <form B>"`, **severity: low**.
- **Inconsistent hyphenation** → title `"Inconsistent Hyphenation: <form A> / <form B>"`, **severity: low**.
- **Inconsistent number style** → title `"Inconsistent Number Style: <form A> / <form B>"`, **severity: low**.
- **Inconsistent tense** → one issue per document, or per section when sections differ, title `"Inconsistent Tense"`, **severity: medium**. Quote one finding in each tense and name the sections involved.
- **Inconsistent tone** → one issue per shift, title `"Inconsistent Tone"`, **severity: medium**. Quote a sentence from each side of the shift.
- **House style compound** → title `"House Style: decisionmaking"`, **severity: low**. List every occurrence.

### Proposed edits

When you can attach proposed edits to an issue, attach one edit per minority occurrence whose fix is fully determined: a term, spelling, hyphenation, number style or house-style compound replaced by the consistent form, or a finding's verb moved to the chosen tense. Quote the sentence, or the exact phrase, verbatim as the text to replace and give the revised text as the replacement. Each edit stays within one paragraph and changes only the variant. Attach edits for up to ten occurrences of a minority form; when there are more, edit the first ten and list the remaining lines in the description. Tone shifts get no edit; the description carries the guidance. When two inconsistencies fall in the same sentence (*Porters' Five Forces* has both an apostrophe and a capitalization variant), attach one edit that fixes both to the first issue and none to the second, and say so in the second issue's suggested action: two edits must never change the same text. Before attaching an edit, reread it against the original: every claim present, every number identical, and the sentence reads naturally in place.

### Volume and coverage

Consistency findings are few by nature: one issue per term family, spelling, hyphenation, number style, compound, tense pattern or tone shift, never one per occurrence. Report up to 20 issues. If the document has more, keep the ones with the most occurrences and summarize the rest in one issue titled `"Inconsistent Term: Further Variants"`, **severity: low**, listing each family in a line.

## Report

In the report deliverable, state which form the document settles on for its findings' tense and its register, how many term families, spellings, hyphenations, number styles and compounds you found inconsistent, how many candidates you set aside as different things or deliberate variation, and which chapters diverged most. Keep it short.
