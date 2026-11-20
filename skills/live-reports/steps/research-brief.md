# Step 4: Research brief

Write the brief as an email to a colleague who knows the report well: what has changed since it was published, what that does to its claims, and how sure we are. Your reader doesn't need the report explained, only what's new. Most readers will stop after the first section, so it must stand on its own; the rest is for those who want to check.

You are given the research plan and the notes: one per fact, data source and angle. The claims weren't researched; judging them is your job. Use only the notes for items in the current plan: a note for an item the plan no longer has doesn't count.

## Judge each claim

The plan lists, for each claim, the facts it rests on, and for each fact, the data it comes from. Work up from the bottom: a newer data release may change a fact, and a changed fact may change what a claim can argue. For each claim, read the verdicts of its facts and decide:

- **Stands:** its facts still hold, or changed in ways that don't touch the argument.
- **Stands, with updates:** the argument still holds, but it should cite newer facts or figures.
- **Weakened:** some of its facts no longer hold, or hold less firmly, and the argument carries less weight or covers less than it did.
- **No longer holds:** the facts it depends on were overturned, and the argument fails without them.
- **Authors' call:** the evidence is mixed or contested, or the claim depends on the authors' own analysis, which would need rerunning on the newer data.

Judge the argument, not the topic. A claim doesn't fall because its field moved on: only when the facts it needs no longer carry it. Some claims survive every change to their facts. When a claim's facts weren't researched or found nothing new, say so instead of judging it.

## Length

Keep everything above the questions for the authors to about 700 words. The notes keep the detail, and the user can ask about any item by its id. To fit, cut background and history first, then detail; never drop a claim that changed.

- Don't restate what the report says beyond the few words needed to name the claim.
- Give the key date and fact of a change, not how it came about.
- One source per point unless a second one settles a doubt.

## What goes in

- **What's new.** One or two paragraphs, at most 200 words: the changes that matter most and what they do to the report's claims, with dates. Write it so that someone who reads nothing else knows what changed and which conclusions it touches. No counts of items researched, no method, no background.
- **Claims affected.** For each claim judged weakened, no longer holds, authors' call, or stands with updates, a few sentences (about 60 words): which facts changed and what is true now, why that weakens it, breaks it or leaves it standing, the confidence, and its strongest source. Order them by how much they matter to the report's conclusions. When more than five claims are affected, write the five that matter most this way and give the others one line each.
- **Where sources disagree.** For each contested fact and each contrary view found, one or two sentences: who says what, since when, and which claim it bears on, with a source for each side. Don't pick a side. Only real disagreements go here: sources about the same thing at the same time that conclude differently. A later source reporting that things have moved on is a change and goes under "Claims affected"; sources that measure differently go there too, with the difference named. Leave the section out when there's nothing to put in it.
- **Claims that stand.** One line listing them by id, with one source for each, unless a claim needs a word of explanation.
- **New developments.** For each angle with significant developments, two or three sentences: what happened, since when, and which claims it touches, if any. Name the angles with minor developments in one line.
- **Questions for the authors.** Two to four questions that only the authors can answer, each in one or two sentences and tied to an id: whether a claim judged "authors' call" still holds, whether two figures on different measures say the same thing, whether to rerun their analysis on newer data, what the research may have missed. Make each one answerable: name the evidence it rests on. Don't ask what the notes already settle.
- **Nothing new found.** One line per fact, data source and angle that found nothing new, with what was searched, so the user can judge whether to dig deeper.
- **Sources.** One numbered list, `[S1]`, `[S2]`…, of the sources the brief cites, without duplicates, with full citations and links. Mark sources published before the cutoff as context. Sources the brief doesn't cite stay in the notes.

## Rules

- Use only what is in the notes and the report. Don't add facts, sources or dates from memory.
- Judging a claim is reasoning, not research: base it on the notes, and make the reasoning visible in a sentence.
- When a note couldn't open a primary source, say so in a clause where it matters.
- Keep the ids next to each claim, fact and angle (`C2`, `F3`, `D1`, `A1`), so the user can ask about any of them.
- Where confidence is low, say so; don't smooth it over.
- When a newer figure is on a different measure from the report's (another scale, benchmark version or setup), say so in a clause, and judge only the direction of the change, not its size.
- If the `voice-and-tone` skill is available, follow it.

## Write `research-brief.md`

```markdown
# Research brief

## What's new

<One or two paragraphs.>

## Claims affected

- **C2, weakened.** <Which facts changed (F3, F4), what is true now, why that weakens the claim; confidence.> [S1]
- …

## Where sources disagree

- **F5, contested.** <Who says what, since when; bears on C3.> [S2] [S5]

## Claims that stand

C1 [S3], C4 [S6].

## New developments

- **A1.** <What happened, since when, and which claims it touches.> [S4]

## Questions for the authors

1. **C2.** <A question only the authors can answer, and the evidence behind it.>

## Nothing new found

- **F7.** <fact, short>. Searched: <what was searched>.

## Sources

- **[S1]** <full citation> <URL>
- …
```

Reply with one line: the path of the brief and the count of claims affected.
