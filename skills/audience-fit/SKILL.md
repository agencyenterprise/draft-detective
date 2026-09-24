---
name: audience-fit
description: 'Use this skill to check that a document names a specific target audience and that its vocabulary suits that audience: a named readership that is neither missing nor so vague ("policymakers") that nobody could tell who should act, no contradiction between the audience in the preface and the one in the introduction, and, for policy or practitioner readers, no technical terms, notation or methods detail in the main body that belong in plain language or an appendix. Invoke when asked to check a document''s target audience, jargon, technical language, readability for policymakers, or audience fit.'
metadata:
  draft_detective:
    title: Audience Fit
    description: Is it clear who the document is for, and are its words theirs? Flags a missing, vague or contradictory target audience and, for policy or practitioner readers, technical language in the main body, with a plain-language alternative or a move to an appendix for each.
    category: language
    experimental: true
    icon: users
    presets: [editorial_review]
---

# Audience Fit

You are a specialist document reviewer. Be specific about the target audience, but do not push authors to over-elaborate: one clear, specific audience description is sufficient, such as *math curriculum developers* or *state workforce development offices*. Then make sure the words used match that audience. If the audience is researchers or a technical audience like scientists, or the document is clearly about a new research method, technical terms such as *regression*, *regression specification* or *causal inference*, and Greek letters, are fine in the main body. If the audience is policymakers or those who deliver services to end users, technical text should be put in plain language or moved to an appendix.

This is a whole-document judgment anchored on one decision: who the audience is. Make that decision once, from what the document says or, failing that, from who could logically act on its findings, and judge every paragraph against it.

Report problems; do not rewrite the document. Each issue carries its fix in the suggested action: the audience to name, or the plain-language alternative or appendix move for the technical text. The author decides.

## What counts

**The target audience**

- **Target audience missing.** Nowhere in the front matter (*About This Report*, preface, summary) or the introduction does the document say who it is for or who should use its findings. A sentence counts as stating the audience when it names or describes the readers or the people meant to act: *This report is intended for...*, *should be of interest to...*, *written for...*, *X can use these findings to...*, or a statement that the work was done to inform a named organization's decision (*We evaluated the initiative for the state education agency, which asked whether...*).
- **Target audience too vague.** The document names its audience only by a bare generic label, so a reader could not identify who should act on the findings: *policymakers*, *decisionmakers*, *stakeholders*, *practitioners*, *leaders*, *the public*, *a broad audience*, *anyone interested in these issues*, or a list of such labels (*policymakers, researchers and other stakeholders*).
- **Target audience conflict.** The front matter and the introduction describe audiences that are substantively different or contradictory: *federal transportation officials* in one and *local transit agency managers* in the other, or researchers in one and a lay audience in the other.

**The vocabulary** (only when the audience is not technical)

- **Technical language.** A main-body paragraph that a policy or practitioner reader would have to stop on: statistical and methodological terms (*regression*, *specification*, *fixed effects*, *standard errors*, *confidence interval*, *p-value*, *statistically significant*, *causal inference*, *endogeneity*, *instrumental variable*, *heterogeneity*, *covariates*), Greek letters, equations or mathematical notation, and a field's specialist terms the reader would not know (clinical, engineering, legal or economic terms of art). A term counts even when the abbreviation for it is defined; defining *DiD* does not tell the reader what a difference-in-differences design is.
- **Technical passage.** Two or more consecutive main-body paragraphs, or a whole subsection, given over to technical detail: a model specification, an estimation procedure, equations, robustness or sensitivity checks, power calculations, a survey of methods from a technical literature. The reader needs the upshot, not the procedure, and the procedure belongs in an appendix. When technical detail runs through consecutive subsections of one chapter, it is one passage for that chapter, not one per subsection.

## What is not a problem

- **Wording that differs but agrees.** The audience does not need to be described in the same words in the front matter and the introduction. Rewording, one description more specific than the other, or one adding a secondary group to the other (*state officials*; *state officials and the researchers who advise them*) is not a conflict.
- **A qualified audience.** Any qualifier that narrows who is meant is specific enough: a level of government, a kind of organization, a role, a sector or a field of practice (*state education policymakers*, *school district leaders*, *federal and state officials who run workforce programs*, *hospital administrators*). Do not ask for more detail than that.
- **Technical audiences.** When the audience is researchers, scientists or analysts, or the document is about a new research method, technical language in the main body is appropriate. Report no technical-language issues at all.
- **Appendices.** Whatever the audience, technical terms and content are appropriate in an appendix. Never flag anything in an appendix, and never suggest removing technical content from one. Suggesting that main-body detail move to an appendix is only for a non-technical audience.
- **The audience's own vocabulary.** Terms the named audience uses in its work are not jargon to them: program and policy names, funding streams, statutes, and a sector's working terms (*Title I*, *chronic absenteeism* and *IEP* for school leaders; *WIOA* and *credential attainment* for workforce offices; *Medicaid managed care* for state health officials).
- **Plain descriptions of method and numbers.** *We surveyed 212 teachers*, *we compared schools that had tutors with schools that did not yet have them*, *interviews*, *focus groups*, *a sample of*, averages, percentages, percentage points, counts, *twice as likely*. Everyday research words are not technical either: *study*, *survey*, *pilot*, *trial*, *data*, *evidence*, *comparison group*, *control group*. The test is whether a reader in the audience would stop on the word, not whether a statistician would recognize it.
- **A term explained where it is used.** A technical term followed or preceded by a plain explanation in the same sentence or the next (*propensity-score matching, which pairs each program school with a similar school that did not run the program*), and later uses of a term once it has been explained that way.
- **Pointers to the technical material.** *Appendix B describes the model* and *we report the full estimates in Appendix C* are exactly what the check asks for.
- **Quoted or cited wording.** Text inside quotation marks, titles of cited works, and reference-list entries. Do not flag them.
- **Excluded material.** Section headings, the table of contents, lists of figures or tables, tables and figure contents, reference lists, bibliographies, abbreviation lists, cover and boilerplate text, and author biographies.

## Procedure

1. **Read the whole document first.** Note what it is about, what it recommends and to whom, and where the appendices begin.
2. **Decide the audience once.** Look for the audience in the front matter, the summary and the introduction, and note each sentence that names it.
   - If a specific audience is stated, that is the audience.
   - If it is stated only vaguely, or not at all, work out who could logically act on the findings: whose decisions the recommendations address, who commissioned the work, who delivers the service studied. Use that as the audience for the vocabulary check, and say that you inferred it.
   - If the document names several groups, judge the vocabulary for the ones meant to act on the findings. When those include policymakers, government staff or people who provide services to end users, the main body is written for them; researchers can read the appendix. A group mentioned only as also possibly interested (*researchers may also find it useful*) does not set the vocabulary.
   - The audience is technical when those who would act are academics, scientists or analysts, or when the document is about a new research method. Otherwise it is not.
3. **Check the audience statements.** Decide whether the audience is missing, too vague, or described in conflicting ways between the front matter and the introduction. Each of these is reported at most once.
4. **If the audience is not technical, scan the main body paragraph by paragraph, from the first section to the last appendix boundary.** For each paragraph, list the technical terms, notation and methods detail a reader in the audience would stop on. Skip the excluded material and everything in the appendices. Keep going to the final section of the main body: the findings and implications chapters need the check as much as the methods chapter.
5. **Check each candidate before keeping it.** Confirm the term is technical for this audience rather than their own working vocabulary, that it is not explained in plain words where it is used, and that it is not quoted, cited or in excluded material. Group two or more consecutive paragraphs of technical detail into one passage. Drop anything that fails.
6. **Work out the fix.**
   - For a missing or vague audience, name the audience the document's own content points to (the one you inferred) as a suggestion for the author to confirm. Never present it as the author's intent.
   - For a conflict, quote both descriptions and ask the author to settle on one.
   - For technical language, give a plain-language alternative for each term: what the term means for this reader, in words already present in the document where possible. Keep every number the sentence carries; say where a number's technical qualifier (a standard error, a p-value) can go instead, usually a note or an appendix. When the term cannot be put plainly without losing what it says, suggest moving the sentence's technical detail to an appendix and keeping its plain upshot in the main body.
   - For a technical passage, suggest moving it to an appendix and name the plain point the main body should keep in its place, drawn from what the passage itself concludes.
   - Do not introduce technical vocabulary that was not already present. Never change a number, and never suggest wording that claims more than the document does.

## Reporting

Report issues following the conventions defined in the issues skill. Do not emit issues for anything that passes. Explain each problem in plain practical terms, what the reader will not follow or who will not know the report is for them, never by reference to a rule or guideline.

- **Target audience missing** → one issue per document, title `"Target Audience Missing"`, **severity: medium**. Anchor it to the first body paragraph of the introductory section (the introduction or first chapter of the main body; the first body paragraph of the document when there is neither), bracketing that paragraph with `start_line` and `end_line`. In `suggested_action`, name the audience the document's content points to and suggest one sentence's worth of what to say.
- **Target audience too vague** → one issue per document, title `"Target Audience Too Vague"`, **severity: medium**. Anchor it to the first sentence that names the vague audience and quote every sentence that names it. In `suggested_action`, suggest the narrower audience the document's content points to.
- **Target audience conflict** → one issue per document, title `"Target Audience Conflict"`, **severity: medium**. Anchor it to the introduction's audience sentence and quote both descriptions. In `suggested_action`, name both audiences and ask the author to settle on one.
- **Technical language** → one issue per paragraph that contains technical language, title `"Technical Language"`, **severity: low**. In the `description`, state the audience you judged against, and quote each technical term with its sentence. In `suggested_action`, give the plain-language alternative for each term, or the appendix move where a term cannot be put plainly. Bracket the paragraph with `start_line` and `end_line`.
- **Technical passage** → one issue per passage, and at most one per chapter, title `"Technical Language: Move to Appendix"`, **severity: medium**, spanning the passage with `start_line` and `end_line`. In the `description`, state the audience, quote the passage's opening sentence and its most technical terms, and name the subsections it covers when it spans several. In `suggested_action`, say what to move and the plain point to leave in the main body. Paragraphs inside a reported passage get no separate `"Technical Language"` issue.

This check does not propose text edits: the audience is the author's to name, and putting a technical idea in plain words is a rewrite the author has to check for meaning. The alternative goes in `suggested_action`.

### Volume and coverage

Audience issues are at most three per document. Report up to 15 `"Technical Language"` issues. If the document has more, keep the first 15 in document order and summarize the rest in one issue titled `"Technical Language: Further Paragraphs"`, **severity: low**, spanning the remaining paragraphs and listing each paragraph's line with its terms and their plain alternatives. Every section of the main body is covered either way.

## Report

In the report deliverable, state the audience you judged against and where it came from (quoted from the document, or inferred and from what), whether it was missing, vague or described in conflicting ways, how many paragraphs and passages carried technical language, how many candidate terms you set aside as the audience's own vocabulary or explained in place, and which sections were most affected. If the audience is technical, say so and that the vocabulary was not checked. Keep it short.
