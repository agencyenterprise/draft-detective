# Step 2: Research plan

Before any searching, agree with the user on what to look for and where. The plan is the research's contract: helpers research exactly the items in it, using the sources it names.

## Map the report

Read the report through the framework in `SKILL.md`: claims rest on facts, and facts rest on data or on the outside world. Map the parts the update depends on.

### Claims

The report's conclusions, findings and recommendations: what the authors argue. List the ones the report's summary and recommendations depend on, and for each one, the facts it rests on. Claims are not researched on the web: once their facts are researched, the brief judges whether the argument still stands.

Give each claim an id, `C1`, `C2`…, and keep it close to the report's wording.

### Facts

The statements the claims rest on that could have changed since publication:

- figures and descriptions of the world, especially dated ones ("currently", "as of", "the latest data", "to date");
- descriptions of laws, policies, programs, institutions and who leads them;
- findings of other research the report relies on;
- forecasts and expectations ("is likely to", "within the next few years");
- the authors' own findings from their data, such as a survey result or a model's estimate.

For each fact, say where it comes from: the **world** (literature, laws, events, other organizations' figures), or the authors' **inference** over data the report names. Skip facts that can't change (definitions, history before the report, the authors' own method) and facts no claim depends on. One fact per idea: if three sentences say the same thing, check it once.

Give each fact an id, `F1`, `F2`….

### Data

The data the report's figures come from: a public statistical series, a survey, a dataset, a benchmark. List the ones that the facts depend on and that may have newer releases. Research looks for the newer release; it doesn't rerun the authors' analysis.

Give each data source an id, `D1`, `D2`….

## Angles beyond the report

Some updates don't change any fact in the report: they are developments the report would cover if it were written today. Add a few angles for those: new laws or policies on the report's topic, events, new data releases, new research directions, new actors. Keep each angle specific enough to search, and give it an id, `A1`, `A2`….

Where one of the report's main claims is a judgment others could dispute, add an angle on other views: whether credible organizations have since reached a different conclusion on the same question ("Other views on C2: …"). Keep it to the claims that matter most; one or two such angles is usually enough.

## Sources

Say which kinds of sources the research should use, fitted to the report's field. For policy research that usually means, roughly in order of weight:

- legislation, regulations and official journals;
- government agencies, their data releases and statistics;
- intergovernmental organizations;
- peer-reviewed research, and reports by established research organizations;
- major news outlets, for events and their dates;
- company announcements, only for that company's own products and decisions.

Name the main official sources for the report's countries and topics where you can (a national statistics office, a legislature's site, a regulator). Exclude what the research should not rely on: unsourced blogs, content farms, AI-generated summaries, press releases presented as evidence for claims beyond the issuer's own actions. Add any files the user provides; they count as sources like any other.

## Size

Aim for 15 researched items or fewer: facts, data and angles together. Claims don't count, since they aren't searched. A report with more candidates needs choices: keep the facts that the most important claims rest on, and list the rest under "Not included" so the user can swap them in.

## Write `research-plan.md`

```markdown
# Research plan

What will be researched, and where, before any searching starts.

## Time window

Published after <publication date>. <If the data ends earlier: for D… and the facts inferred from them, anything after <data-through date> counts as new.>

## Claims

What the report argues. Not searched: the brief judges them from their facts.

- **C1 (<section>).** "<the claim, quoted or closely paraphrased>" Rests on F1, F3.
- …

## Facts to check

- **F1 (<section>).** "<the fact, quoted or closely paraphrased>" From: <the world | inference over D1>.
- …

## Data

- **D1.** <the series or dataset, its publisher, and the edition or year the report used>
- …

## Angles beyond the report

- **A1.** <a development to look for>
- …

## Sources

- <kinds of sources, with named official sources where known>

## Not used

- <kinds of sources to avoid>

## Not included

- <candidate facts, data or angles left out, if any>
```

Leave out a section that has nothing in it, such as Data for a report built on literature alone.

Then tell the user how many items will be researched and what that will take: each item means several minutes of searching and reading and dozens of searches, so the time and cost grow with every item, even when items run in parallel. Ask them to add, drop or change claims, facts, data, angles or sources before you start searching.

When the user asks for a change, edit the plan in place and keep the ids of the items that stay, so earlier references still make sense. A new item takes the next free id of its kind.
