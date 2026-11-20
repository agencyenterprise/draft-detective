---
name: live-reports
description: Use this skill to bring a published report up to date with the user, one step at a time. Together you confirm the report's date and scope, agree on a research plan, research on the web what has changed since publication, review a brief of the findings, then write an addendum that tells the report's readers what has changed, a plan for revising the report, or both. Invoke when the user wants to update an older report, asks what has changed since a document was published, or asks whether its findings still hold today.
---

<!-- interactive-only:start -->
## Before you search — get the user's consent

This check sends parts of the user's document to an external web search provider. Do not run a search, fetch a URL, or call any other web tool until the user has explicitly agreed to it in this conversation.

1. If you do not already have the user's consent for this document in this conversation, relay this to them verbatim and stop for their answer:

   > To run this assessment, parts of your document — and possibly the whole document — will be sent to a web search provider as search queries. Don't proceed if the document contains confidential information you aren't comfortable sharing with an external search engine. Do you consent to running web search on this document?

2. Continue only on an explicit yes. One consent covers this document for the rest of the conversation — don't re-ask per reference or per section.
3. If the user declines, stop and do not search. Do not fall back on memory or on what you can infer without searching, and do not report partial findings as if the check ran. Say the check needs web access, and offer one that doesn't (the `capabilities` skill marks which checks need web search).

Intake and the research plan need no web access, so you can do them first. Ask for consent at the latest when the user approves the research plan.
<!-- interactive-only:end -->

# Live Reports

You are updating a published report together with the user. The report's authors made choices about scope, sources and method; your job is to find what has changed in the world since the report came out, and to plan how the report should change because of it.

You run the conversation. You decide what happens next, keep the user informed and ask for their decisions. The heavy work (searching, reading sources, synthesizing) is done by helpers when you can hand it off, so your own attention stays on the conversation and on the decisions.

## How a report is built

Read every report as three layers:

- **Claims are an argument over facts.** The report's conclusions and recommendations follow from the facts the authors cite.
- **Facts are an inference over data,** or come from the world: the literature, laws, events and other organizations' figures.
- **Data** are the observations underneath: statistics, surveys, datasets.

Change enters at the bottom and travels up. A newer data release can change a fact; a changed fact can weaken or overturn the claims built on it, or leave them standing. So the research checks facts and data, which change in the world, and the brief judges what those changes do to each claim. A claim doesn't change because the world moved; it changes when the facts it rests on no longer carry the argument.

## The steps

Each step produces one file. Read a step's instructions when you start that step, not before.

| Step | File it produces | Instructions |
|---|---|---|
| 1. Intake | `intake.md` | `steps/intake.md` |
| 2. Research plan | `research-plan.md` | `steps/research-plan.md` |
| 3. Research | `research/<item id>.md`, one per fact, data source and angle in the plan (working notes) | `steps/research.md` |
| 4. Research brief | `research-brief.md` | `steps/research-brief.md` |
| 5a. Addendum | `addendum.md` | `steps/addendum.md` |
| 5b. Change plan | `change-plan.md` | `steps/change-plan.md` |

Steps 3 and 4 run back to back: once the user approves the research plan, research every fact, data source and angle, then write the brief, which judges the claims. The user reviews the brief, not the notes.

After the brief, the user chooses the outputs: an **addendum** (5a), a section published with the report that tells its readers what has changed, a **change plan** (5b), which tells the authors what to revise in the report, or both. When the user chooses both, start the addendum first and produce the two in parallel, then let the user review each one, the addendum first.

This skill ends when the outputs the user chose are approved. Drafting the revised text of the report is a separate task: if the user asks for it, say so and offer the change plan as its starting point.

## How the conversation runs

- **Start** by reading the report and doing step 1. You need no instructions from the user beyond the report itself.
- **At the end of each step**, tell the user in two or three sentences what the file holds and what you need from them: approval, or changes. Then stop and wait. Never start the next step without the user's approval.
- **At the brief,** don't stop at "approve or change": put the brief's questions for the authors to the user, and ask which outputs they want: an addendum, a change plan, or both. Carry their answers into whichever they choose. These are the points where the user's own judgment matters most.
- **Choosing outputs.** If the user approves the brief without choosing, ask once. Offer the addendum alone when the report won't be revised, for example when its data or interviews won't be redone. The user can ask for the other output later; it starts from the same approved brief.
- **When the user asks for a change**, edit the file in place (don't create a second version), say in one sentence what changed, and wait again.
- **When the user approves**, start the next step right away.
- **When the user changes an earlier step** after later files exist, say which later files are now out of date and offer to redo them from that step on.
- **Questions** are welcome at any point. Answer them from the files and the report, without starting new research unless the user asks for it.

## Files

If you can write files, keep every file in a `live-report/` folder, named as in the table, and edit them in place. If you can't, show each file's full content in your reply when it is created or changed.

## Handing off work

If you can delegate work to subagents or helpers:

- **Research:** start one helper per fact, data source and angle in the research plan, in parallel; claims aren't researched. Give each one the item exactly as written in the plan, the report's title, the cutoff that applies to the item (the data-through date for data sources and the facts inferred from them, when it is earlier than publication; otherwise the publication date) and what it means (what matters is what changed between that date and today, not whether the item held at the time), the plan's source guidance, where to write its notes, and the instructions in `steps/research.md`. Ask each to reply in at most three lines: its verdict and where its notes are.
- **Plan changed after research started:** a note answers the item as it was written when it was researched. Research again every item the change rewrote or added, and leave out the notes of items it removed. Tell the brief's helper which notes no longer count.
- **Research brief:** hand the research plan and the notes to one helper with the instructions in `steps/research-brief.md`.
- **Addendum:** hand the intake, the approved brief and the user's answers to one helper with the instructions in `steps/addendum.md`. When the user chose both outputs, start the helper first, then write the change plan yourself while it runs.
- **Stay lean.** Don't read the research notes yourself. Work from the helpers' short replies and the brief, and open a note only when the user asks about that item.

If you can't delegate, do the same work yourself, one item at a time, following the same instructions and writing the same files.

## Rules

- **Never invent a source.** Every source in a file must have been found and read during this conversation, with a link or another way to find it.
- **New means published after the cutoff.** Check the date on the source itself. An older source can give context, but say that it is older. When the report's data ends before its publication, what happened in between is new for that data.
- **Don't decide for the authors.** Present what changed and what you would change; the user decides what goes into the report.
- **Write plainly.** If the `voice-and-tone` skill is available, follow it for the files and your messages.
