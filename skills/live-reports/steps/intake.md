# Step 1: Intake

Establish what the report is, when it was published, when its data ends, and what the update covers. Everything later depends on these dates: they are the cutoffs after which material counts as new.

## What to find

- **Title and authors.**
- **Publisher** and, if given, the report's series or number.
- **Publication date.** Look at the cover, the front matter, the copyright line and the citation suggested in the report. If you find only a year, say so. If you find nothing, ask the user; don't guess.
- **Data through.** The date the report's data ends: its newest observation, survey wave, model, release or event, from its tables, appendixes and "as of" statements. Reports often go to press months after their data closes. If it ends noticeably before publication, record it: what happened in between is new too, even though it predates the report. If you can't tell, say so.
- **Sections.** The report's main sections, by their headings.
- **What the conclusions rest on.** Most reports argue from facts drawn from literature, policy, interviews and events, which web research can update. Some draw facts from data through their own analysis. Name the data sources the report uses (a public statistical series, a survey, a dataset, a simulation): the research can look for newer releases of public data, but updating the authors' own estimates means rerunning their analysis, which this process does not do.

## Scope

By default, every section of the body is in scope. Front matter, references and appendices are out of scope unless the user says otherwise. The user may also narrow the scope to some sections or topics.

## Write `intake.md`

```markdown
# Intake

- **Title:** …
- **Authors:** …
- **Publisher:** …
- **Published:** <date, as precise as the report allows>
- **Data through:** <date, or "same as publication", or "unclear">
- **Cutoff for new material:** published after <publication date>; for the report's data and the facts inferred from it, after <data-through date>, if earlier

## In scope

- <section heading>
- …

## Out of scope

- <front matter, references, appendices, or what the user excluded>

## Notes

- <what the conclusions rest on: the kinds of facts, the data sources named, and anything this process can't update>
```

Then tell the user the dates you found and the scope, and ask them to confirm or correct them.
