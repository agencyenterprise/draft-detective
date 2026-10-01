---
name: review-assistant
description: >-
  Helps authors work through a peer-review cycle: making sense of what the
  reviewers asked for, planning the revision, and writing the paperwork that
  closes the loop with the reviewers and the quality-assurance manager. Use it
  whenever someone has a draft plus one or more reviewer memos (also called
  review reports, referee reports, or reviewer comments) and needs to act on
  them: to understand or organize the feedback, plan revisions from it, respond
  point by point, or check whether a revised draft addresses what was raised.
  Produces, singly or together: a revision-planning summary, one response memo
  per reviewer, and a consolidated reviewer coverage report for a QA manager.
  Trigger even when the user does not say "skill" or name an output: "respond to
  these reviewer comments", "draft a response memo to the reviewer", "did my
  revision address the review", "what does this reviewer want me to change",
  "check my responses cover everything the reviewers raised", "help me deal with
  this referee report".
---

# Review Assistant

## What this skill does

Research reports and similar publications go out for peer review. Each reviewer
returns a memo, and the authors then write a revised draft plus a response memo
per reviewer explaining how they handled each point. A quality-assurance
reviewer, called the QA manager (QAM) here, signs off on whether the authors
were responsive. This skill automates the author-side and QAM-side paperwork of
that loop from the documents the author already has.

It produces three outputs. You do not have to produce all three every time.
Read what the user is asking for and produce the ones that fit, but they share
the same foundation (parsing the memos and locating each point in the draft), so
build that once and reuse it.

- **Revision-planning summary.** Earliest in the cycle. From the
  original draft and the reviewer memos, list the topics the reviewers want
  changed, where each sits in the draft, and a short suggestion for addressing
  it. This is an orientation aid the author uses before revising.
- **Reviewer response memos, one per reviewer.** From the original
  draft, the revised draft, and the reviewer memos, draft a response memo for
  each reviewer that echoes every reviewer point and states how the revision
  addressed it (or why it was not changed).
- **Reviewer coverage report.** For the QAM. From the original draft,
  the revised draft, the reviewer memos, and the response memos, consolidate
  everything the reviewers asked for and whether and how each item was
  addressed, with an overall responsiveness read.

## Inputs

Ask for or identify what you have. Not all inputs are needed for all outputs.

- **Original draft**: the version that was reviewed. Needed for all outputs.
- **Reviewer memos**: one or more. Can be any text-based format, though usually
  Word or PDF. Needed for all outputs.
- **Revised draft**: the version that addresses the comments. Needed for the
  reviewer response memos and the reviewer coverage report.
- **Response memos**: the author's replies. If they already exist they are an
  input to the reviewer coverage report; if they do not, the coverage report can
  run on the revised draft alone, and the reviewer response memos produce them.
- **Reviewer marked-up copy** (optional): a copy of the report with inline Word
  comments and tracked edits. Treat these as secondary and editorial (see
  "Word comments" below).

The documents in one cycle are small enough to hold at once: memos and response
memos run roughly 800 to 1,700 words, and a full report is around 12,000 words.
Do not chunk them. Read each in full so cross-references resolve.

## The shared foundation

Do these two steps first, whatever output you are producing.

### 1. Parse each reviewer memo into discrete points

Reviewer memos have no standard layout, so do not expect a particular header,
section name, or ordering, and do not force the memo into a template. Read it
whole and work from what it actually contains. Some memos open with a header
block, a rating, or an overall assessment before the feedback starts; others go
straight in.

The substantive feedback is where the real work is. Two shapes are common:

- **Hierarchical**: thematic headers (for example "Methodological Justification")
  with bullets, sometimes nested sub-bullets. One bullet is usually one point.
- **Flowing prose**: paragraphs with no headers, where each paragraph is one
  point.

These are patterns to recognize, not an exhaustive list. A memo may mix them or
take another form entirely: a numbered list keyed to page numbers, a table, a
commentary that walks the document section by section. Handle whatever shape you
are given. Feedback also often continues past the main section, under a heading
such as "Additional suggestions" or "Minor comments", so work through the memo
end to end.

Segment the feedback into discrete, individually addressable points. A point is
one thing the author could act on. Split compound bullets that bundle several
asks. Preserve the reviewer's own wording for each point, because the response
memo will echo it.

Assign each point a stable **ID** and use it in every output. Give each reviewer
a letter in the order their memos are provided (the first reviewer is A, the
second B, and so on), and number that reviewer's points in memo order: A1, A2,
A3 for the first reviewer, B1, B2, B3 for the second. Use sub-point IDs (A1.1,
A1.2) only when a single point genuinely contains distinct sub-asks worth
tracking separately, such as a bullet with nested sub-bullets; do not force them
otherwise. Once assigned, an ID always refers to the same point. The
revision-planning summary, the reviewer response memos, and the reviewer
coverage report all cite these same IDs, so a reader can trace one point across
every document.

### 2. Locate each point in the draft

Reviewers point to places loosely: by page ("around page 8"), by named concept
or section ("Model 5", "the fourth model"), by figure, or at the whole report.

The important trap: **numbers and headings move between the original and revised
draft.** Authors reorder and rename sections in response to reviews. A point
that referenced "Concept 4" in the original may be a differently numbered and
retitled section in the revised draft. So map points by **semantic anchor**, the
topic or concept the point is about, not by page number, section number, or
heading text. When you report a location, describe it by content ("the section
introducing the five concepts") so it survives renumbering, and verify presence
by matching meaning, not position.

Classify each point's scope, since it changes what the tool can check:

- **Document-wide** (applies to the whole document or its framing),
- **Section-level** (a chapter, concept, or named part),
- **Paragraph-level or local** (a specific passage, figure, or sentence).

## Word comments and marked-up copies

If a reviewer returned a marked-up copy with inline Word comments, treat those
as editorial and lower authority than the memo. The memos say as much
explicitly: inline suggestions that are not repeated in the memo are
non-binding, and the author may decide how to respond. Attach a marked-up copy
to its reviewer's memo. Surface its comments only as optional, clearly
secondary, and never let an unaddressed inline comment lower the responsiveness
read the way an unaddressed memo point does.

## Include the reviewer memo verbatim in every output

Every output this skill produces must reproduce the reviewer's original memo in
full and verbatim, not paraphrased or summarized away. The reviewer's exact
words are the anchor of the whole exchange, and authors, reviewers, and QAMs
need to see them unaltered so they can trust that nothing was dropped or
reworded. This applies to all three outputs, including the planning summary and
the coverage report, not just the response memos.

Make the boundary between the reviewer's words and your own contribution
unmistakable. Never blur the two, and never present your own wording as if the
reviewer wrote it.

- **Mark quoted text clearly.** Use whatever the output medium provides: a
  Markdown blockquote (each line prefixed with `> `), an HTML `<blockquote>`
  styled to stand apart from the surrounding text, or in a Word deliverable a
  visually distinct, labeled "Reviewer (verbatim)" block. Reproduce the memo in
  full, including any header or rating block and any trailing sections of
  additional or minor suggestions.
- **Match the original formatting where you can.** Beyond the text, try to carry
  over the reviewer's own formatting: headings, bullet and numbering structure,
  bold and italic, indentation, tables. The closer the reproduction looks to the
  source, the more easily the author can visually anchor each item back to the
  original document. If the output medium cannot reproduce a formatting element
  faithfully, keep the text and structure and do not let anything drop.
- **Put your contribution next to each point.** After each quoted point, add your
  own content for it (the suggestion, the author's response, or the verdict and
  evidence, depending on the output), clearly labeled and outside the quote.
- **Open with Part 1, the summary.** Every output leads with a short summary
  that stands on its own, placed before the reproduced memo and the
  point-by-point content. See "Lead with the decision, demote the detail" below
  for what belongs in it and, just as importantly, what does not.
- **Preserve the reviewer's order and wording.** Reproduce the memo in the
  reviewer's own order, and do not drop, reorder, or reword any of the reviewer's
  text.

The per-output sections below say what your contribution next to each point
should contain. The verbatim reproduction and clear marking are constant across
all of them.

## Lead with the decision, demote the detail

Reproducing every memo in full makes these outputs long by design. That is the
right trade for trust, but it leaves the reader's actual decision sitting behind
pages of material they may not need. So lay every output out in two parts, and
make the split explicit on the page:

- **Part 1, the summary.** What the reader has to act on. It stands alone: a
  reader who stops here has everything they need for their next decision. Keep
  it to roughly one printed page.
- **Part 2, the point-by-point detail.** The reviewer memos reproduced verbatim
  with your contribution under each point. Label it as reference material to
  consult, not a section to read through.

Say this on the page. Under the Part 2 heading, add a line noting that it
reproduces every reviewer point in full (and, in a coverage report that has the
author's response memos, the author's reply to each) and is there for reference,
so no reader concludes that something was dropped from Part 1.

**Part 1 is decision-grade, not descriptive.** The failure mode is a summary
that retells the memos in shorter words, which adds length and saves nobody any
reading. Part 1 earns its place only by naming what still needs someone to do
something. Two rules keep it honest:

- **Name the exceptions, not the full set.** Anything already settled belongs in
  Part 1 as a count and nowhere else. In the coverage report that means an
  `addressed` or `declined with rationale` point never gets a line of its own,
  however interesting the reasoning behind it.
- **One line per item, then point into Part 2.** Give the point ID, the ask in
  the reviewer's terms, and what is missing or needed. The evidence, the
  reviewer's full wording, and your reasoning live in Part 2, and the ID is the
  reader's way back to them.

The per-output sections below say what each Part 1 contains. The reviewer
response memos are the one exception to this layout, for the reason given in
their section.

## Tone and voice

Everything this skill writes should sound like an experienced research
colleague, not a generic assistant. Reviewer response memos, revision plans, and
coverage reports share a specific register: collegial and plain, anchored in the
text, opinions owned in the first person, critiques framed as suggestions or
questions, and declines given with a clear reason rather than an apology or
reflexive agreement.

Before drafting any prose output, load the `voice-and-tone` skill and follow it.
It has separate guidance for the critique voice and the author voice, phrase
banks, and a list of generic-AI tells to avoid (sycophancy, hype, empty hedging,
exclamation marks, em dashes, emoji).

Which voice applies depends on who is speaking in the output. The response memos
are written as the author, so they use the author voice. The revision-planning
summary and the coverage report are your own assessment, so they use the
critique voice and stay neutral and evidence-anchored.

## Revision-planning summary

Goal: help the author see the whole ask before revising. Inputs: original draft
and reviewer memos.

**Part 1** is the author's worklist, not a description of the feedback. The
decision it has to support is what to work on and in what order, so give the
author:

- **Conflicts between reviewers**, first. Where two reviewers want incompatible
  things, name both point IDs and say what has to be settled. Only the author
  can resolve these, so nothing sits above them.
- **The substantial asks**, as a short ordered list: point ID, the ask in one
  line, and where it lands in the draft (by content, per step 2). These are the
  points that need real work rather than an edit.
- **The quick fixes**, reduced to a count and their point IDs. Do not spell them
  out; each is already one line in Part 2.

**Part 2** reproduces the reviewer memo(s) in full, verbatim, following the
reviewer's own structure, with each point labeled with its ID (see step 1).
Directly under each quoted point, add a compact planning note with:

- its scope,
- where it lives in the draft (by content, per step 2),
- a one or two sentence suggestion for how to address it.

This is a planning aid, so keep your added notes brief even though the reviewer's
text is reproduced in full.

## Reviewer response memos

Goal: one response memo per reviewer, in the form authors write by hand.
Inputs: original draft, revised draft, reviewer memos.

This is the one output that does not use the two-part layout from "Lead with the
decision, demote the detail". The response memo is an outbound document
addressed to the reviewer, and a summary panel written for the author would read
wrong in a letter to somebody else. The courtesy preamble already gives the
reviewer their bearings.

The response memo is a near-mechanical transform of the reviewer memo: clone the
memo and interleave the author's replies. Follow this shape, which mirrors what
authors actually produce:

1. Reuse whatever header the memo uses, reframed as a response (for example a
   "Re:" line becomes "Response to Review of ..."). Keep any rating or
   overall-assessment block the memo has.
2. Open with a short courtesy preamble and state how the author's replies are
   distinguished from the reviewer's text (see formatting below). It is common to
   also restate the reviewer's overall-assessment paragraph. Follow the preamble
   with a short summary written for the reviewer: how the revision responded to
   them overall, the main changes their comments produced, and anything
   deliberately not changed, so the reviewer sees the shape of the response
   before the point-by-point replies. This stands in for Part 1 in this output,
   so keep it to a paragraph or two.
3. For every point in the reviewer's memo, in the reviewer's order, label it
   with its ID (see step 1), echo the reviewer's original text verbatim as a
   clearly marked quote, then add the author's response directly after it in a
   clearly differentiable way. Reproduce the entire memo this way, including any
   trailing sections of additional or minor suggestions, so nothing is dropped
   (see "Include the reviewer memo verbatim in every output").

For each response, compare the revised draft against the original to determine
what actually changed, and write the reply accordingly:

- If addressed, say concretely what changed and where, and quote the new text
  when short (for example, the new opening sentence of a section).
- If partially addressed, say what was done and what was not.
- If not changed, give the reason. Reasoned declines are normal and expected,
  not failures. Common and legitimate grounds include the document type (see
  below), scope, and disagreement with the reviewer. Write these plainly and
  respectfully.

When you cannot write a real response to a point because nothing in the revised
draft addresses it and there is no stated reason, flag it for the author rather
than inventing a change. That flag is the signal that prompts another revision.

Collect those flags into a single block at the very top of the deliverable,
above the first memo, headed so that it is unmistakably internal: it is
addressed to the author, and it has to be deleted before the memo is sent. Give
one line per flagged point, with its ID and what is missing, style the block to
stand apart from everything else in the document, and repeat the "remove before
sending" instruction inside it. Keep the flags out of the body of the memos,
where they would otherwise go out to the reviewer. If there are no flags, leave
the block out entirely.

Produce one such memo per reviewer. Do not generate the reviewer memos
themselves, and do not edit the draft.

## Reviewer coverage report

Goal: one consolidated view for the QAM. Inputs: original draft, revised draft,
reviewer memos, and response memos.

The QAM has one decision to make: sign off, or send the revision back for
another pass. Part 1 exists to answer that and nothing else.

**Part 1, the summary.** In this order:

1. **Header and verdict.** A title, the document type (see below), and the list
   of reviewers, then the overall responsiveness read in a line or two and an
   explicit recommendation: sign off, or return for another pass.
2. **What needs another pass.** The critical list, and the centerpiece of the
   page. Include every `not addressed` point, and every `partially addressed`
   point whose remainder is consequential. One line each: the point ID, what the
   reviewer asked for, and what is still missing. When there is nothing, say so
   in one line rather than dropping the section.
3. **Summary verdict table.** A table with the count of points in each verdict
   category: addressed, partially addressed, declined with rationale, and not
   addressed. Give the totals, and break the counts down per reviewer when there
   is more than one. List the point IDs alongside each category's count so the
   QAM can jump straight to them in Part 2.

Nothing else belongs in Part 1. A point that is `addressed` or `declined with
rationale` is settled: it is counted in the table and its ID appears there, but
it gets no entry of its own outside the table, and no account of what changed or
why. That belongs in Part 2.

**Part 2, each reviewer's memo, verbatim, with your verdicts interleaved.** For
each reviewer in turn, reproduce their memo in full and verbatim as a clearly
marked quote (see "Include the reviewer memo verbatim in every output"), in the
reviewer's own order, labeling each point with its ID (see step 1). Directly
under each quoted point, record your assessment: the verdict, the point's
location in the draft by content, and brief evidence (what changed in the
revised draft, or the author's stated reason for not changing it).

When you have the author's response memos, reproduce the author's reply to each
point verbatim as well, directly under the quoted reviewer point and before your
assessment. Mark it as a separate, labeled quote ("Author response (verbatim)")
styled so it cannot be mistaken for the reviewer's text. Copy the reply as
written, without trimming or merging it. When no reply answers a point, say "No
author response to this point" in that slot rather than leaving it out. The QAM
then sees, for every point, what the reviewer asked, what the author said, and
what the draft shows, in that order.

Use a verdict scale that reflects how real responses look, not a binary:

- **addressed**: the revision resolves the point.
- **partially addressed**: some of the point was handled.
- **declined with rationale**: deliberately not changed, with a stated reason
  (scope, document type, disagreement).
- **not addressed**: no change and no reason. This is the only verdict that
  should read as a gap.

When you have the author's response memos, read each point's reply alongside
the draft comparison. The reply supplies the author's stated reason for a
decline and says where they made a change, but the revised draft is the
evidence. Check every claimed change against the draft. If the reply says a
point was handled and the draft does not show it, the verdict follows the draft,
and your note says what the reply claimed and what the draft shows. The QAM
most needs to see these discrepancies, so a consequential one also belongs in
"What needs another pass". A point that no reply answers is judged on the draft
alone. When you have no response memos, say so in the header, since every
"declined with rationale" verdict then rests on reasons you inferred from the
draft rather than on reasons the author gave.

Be document-type aware, because it changes what "responsive" means. A short
perspective, commentary, or expert-opinion piece is shorter and more
opinion-oriented than a formal research report, so many substantial asks are
legitimately declined as out of scope. Judge responsiveness against what the
document is, not against an ideal of addressing everything.

When two reviewers raised the same underlying point, do not drop either memo's
text, since each memo is reproduced in full. Instead note the overlap in your
assessment, referring to the other point by its ID (for example "also raised as
B3"), so the QAM can see the counts are not double-weighting the same concern. Overlap is common on themes
like methodology and premise.

## Formatting conventions

These outputs are usually delivered as Markdown, HTML, or a Word document. The
conventions below are the same in all three; only the mechanism differs, so pick
the one the medium you were asked for actually supports.

- **Distinguish quoted reviewer text from your additions.** Reviewer text is
  reproduced verbatim and clearly marked as a quote: a Markdown blockquote, an
  HTML `<blockquote>` that is visually set off (an indent plus a rule or tinted
  background), or a labeled and visually distinct block in a Word deliverable.
  Your own content sits outside the quote under a clear label. This boundary must
  hold in every output (see "Include the reviewer memo verbatim in every output").
- **Make author replies clearly differentiable.** In response memos, and in a
  coverage report that reproduces the author's replies, the reader needs to tell
  the author's reply from the reviewer's text (and, in the coverage report, from
  your assessment) at a glance. Choose a
  method the output format actually supports: colored text (blue is a common
  convention) works in a Word deliverable; Markdown has no color, so use a clear
  textual marker instead, such as a bold "Response:" label; HTML can do both, and
  should, since styling alone disappears when a report is printed to PDF, viewed
  in black and white, or copied out as plain text. Never let the distinction rest
  on color alone. Whatever you choose, apply it consistently.
- **Carry over the memo's own header and any rating block.** Memos do not share a
  fixed layout, so reproduce whatever header the memo uses rather than imposing a
  standard one, and reproduce any rating or overall-assessment block when one
  appears.
- **Describe locations by content, not by number**, for the reasons in step 2.
- **When the output is HTML, style it as a finished document.** Give it a
  readable measure and type scale, real table styling for anything tabular, and
  visible hierarchy between headings, quoted reviewer text, and your own
  contribution. Assume it will be read on screen and printed to PDF, so it has
  to hold up in black and white as well as in color.
- **Make the Part 1 / Part 2 split visible.** Give each part a heading that says
  what it is, and label Part 2 as reference material. Start Part 2 on a new
  printed page (in HTML, `break-before: page` on the Part 2 heading) so that
  Part 1 is literally the first page when the report is printed to PDF. Style
  Part 1 as a summary panel rather than as the opening section of a long report.
- **Do not hide Part 2 behind a control that printing cannot open.** These
  reports get printed to PDF, and a collapsed `<details>` prints collapsed,
  which would drop the verbatim memo from the PDF. The page break above is what
  demotes Part 2. If you add a disclosure widget on top of that, pair it with a
  print rule that forces it open.

## Related skills

- `voice-and-tone`: how to sound like an experienced research colleague. Load it
  before writing any prose output (see "Tone and voice" above).
