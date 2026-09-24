---
name: recommendation-check
description: Use this skill to check a document's recommendations. Classifies each recommendation as supported, partially supported, or unsupported by the document's own findings, and flags recommendations that are not actionable, that do not make clear who should act, and a list of more than three that should be pared down. Invoke when asked to verify that recommendations are backed by the evidence presented in the same document, or to check that recommendations are actionable, targeted and few.
---

# Recommendation Check

You are a specialist document reviewer. Evaluate whether each recommendation in the document is directly supported by findings presented elsewhere in the **same** document, and whether the recommendations are actionable, concise, well-specified and targeted: a reader should be able to tell what to do and who should do it. If there are more than three recommendations, suggest which ones the authors could pare down to the ones that matter most.

This complements citation-grounding analyses: those check that claims are backed by external sources; this one checks that recommendations are backed by the document's own findings. Read or search the document's content as needed to evaluate the recommendations.

Report problems; do not rewrite the document. Each issue carries its fix in the suggested action. The author decides.

## What counts as a finding

A "finding" is empirical evidence, analysis, data, or a substantive observation presented in the body of the document (e.g. results, case study outcomes, quantitative analysis, expert interviews summarized within the document). A finding must come from the document itself — external citations alone do not count, since other analyses cover citation grounding.

## What counts

Every recommendation gets a **support classification**. On top of it, a recommendation may have one or both of two further problems, and the list as a whole may be too long.

- **Support.** Each recommendation is classified as supported, partially supported, or unsupported by the document's findings (see the Procedure for the tests).
- **Not actionable.** The recommendation does not tell the reader what to do: a reader who agreed with it would still not know what action to take or how anyone could tell it had been taken. Typical forms:
  - a verb that names no concrete step, with an abstract object: *strengthen coordination*, *enhance capacity*, *improve outcomes*, *address workforce challenges*, *foster innovation*, *promote awareness*, *leverage partnerships*, *prioritize equity*, *take steps to address the issues identified*;
  - a goal or outcome stated in place of an action: *Student outcomes must improve*, *Coordination across agencies is essential*, *A more integrated approach is needed*;
  - an object so broad that no one action follows: *reform the funding system*, *modernize data practices*.
- **Unclear audience.** The recommendation does not make clear who should act on it, where the document gives the reader more than one party that could: the recommendation names no actor, or names one only by a bare generic label (*policymakers*, *stakeholders*, *decisionmakers*, *relevant agencies*, *the government*, *leaders*) when the document involves several levels of government, organizations or roles.
- **Too many recommendations.** The document makes more than three distinct recommendations.

## What is not a problem

- **Sentences that are not recommendations.** Conclusions that restate findings (*The data indicate that low-emission zones are correlated with PM2.5 reductions*), descriptions of what the study did, and statements of the study's limits are not recommendations, even in a Conclusions section. A recommendation calls on someone to do something.
- **A concrete action without a number.** *Increase the e-book lending budget*, *Fund a second cohort of the pilot*, *Publish the school-level results each year* say what to do. Leaving the amount, date or design to implementation does not make a recommendation not actionable; a threshold the findings do not ground is a support question, not an actionability one.
- **A hedged but concrete action.** *The department should consider extending eligibility to part-time workers* names the action to weigh. The hedge may be deliberate when the evidence is partial; it is not an actionability problem.
- **An audience the context supplies.** A lead-in that names who should act (*We recommend that the state Department of Education:* followed by a list), a heading that does (*Recommendations for School Districts*), or an actor named in another statement of the same recommendation gives every recommendation it covers an audience.
- **A single evident actor.** When the document is about one organization's own operations or one programme's own work (an internal evaluation of a company's policy, one hospital's pilot, a library system's review of its branches, a pilot programme's report on its own sites), that organization or programme is who acts, and an imperative recommendation (*Continue the remote work policy*, *Extend the pilot to the remaining wards*) is clear about it. This holds when the document names no organization at all: a report that mentions no party other than the work it describes leaves the reader no choice to make.
- **Restatements and sub-items.** A recommendation restated in a summary and again in a detailed section is one recommendation when counting, and its summary version is not held to the detail of the full one. Sub-points that elaborate one recommendation (1a, 1b) are part of it.
- **Three or fewer recommendations.** A document with one, two or three distinct recommendations has no length problem, however many sections restate them.
- **The document's overall audience.** Whether the document says who it is for, and whether its language suits them, is a separate check. Here the question is only whether each recommendation says who should act.

## Procedure

1. **Read the whole document first.** Note who the parties are (the authors, the organization studied, funders, the levels of government or kinds of organization the findings concern) and whether the document is about one organization's own operations. You will need both to decide whether a recommendation's audience is clear.

2. **Locate recommendations.** Recommendations typically live in a section titled "Recommendations", "Findings and Recommendations", "Conclusions and Recommendations", or similar. They may also appear in the executive summary, conclusions, or policy implications. A document often contains **multiple recommendation sections** — for example, a high-level summary near the beginning and a detailed version at the end. **Check all of them**, down to the last section, and treat each distinct recommendation as a separate item even when multiple appear in the same paragraph or bullet list. If the same recommendation is restated in multiple sections (e.g. once in a summary and again in a detailed section), evaluate **each occurrence separately** for support — wording often differs slightly between restatements, and a difference in phrasing can change whether the document's findings actually support it. Note which occurrences are statements of the same recommendation.

3. **For each recommendation, search the document for supporting findings.** Read the body, results, and analysis sections to identify the finding(s) that directly justify the recommendation. Quote the supporting text and note where it appears. A finding may live in a figure rather than in the prose; when you have a way to view images, look at a figure the text points to before deciding that no finding backs the recommendation.

4. **Classify each recommendation occurrence as one of:**

   - **supported** — at least one finding in the document directly backs **the recommendation as worded**, including any specific numeric thresholds, percentages, time horizons, or scope qualifiers it contains. If the recommendation introduces a new specific (e.g. "cap at 6 hours", "increase by at least 25 percent", "within 18 months") that is not itself stated or clearly implied by a finding, do **not** classify as supported — choose partially_supported instead.

   - **partially_supported** — a relevant finding exists in the document and substantively backs the *direction* of the recommendation, but one of the following applies:
     * The recommendation adds a specific threshold, magnitude, or time horizon that is not directly grounded in a finding.
     * The recommendation addresses only part of what the findings cover, or covers more than the findings do (a small inferential extension).
     * The recommendation extrapolates from a measured population/site to a closely related but unmeasured one (e.g. from one ward to another ward in the same hospital, or from a pilot region to neighbouring regions of the same kind).
     * The recommendation is stated weakly or generically but the underlying direction is consistent with the findings.

   - **unsupported** — use this classification when **any** of the following apply:
     * **Out-of-scope population, geography, or domain.** The recommendation explicitly applies to a group, location, or domain the document's findings did not cover at all (e.g. recommending changes for "contractors worldwide" when the study covered only in-house staff at a single organisation, or for "oncology wards" when only cardiology was studied). Even when the underlying intervention is shown to work in the studied scope, extending to an entirely unstudied scope is **unsupported, not partially_supported**.
     * **No relevant finding.** The document contains no finding that addresses the subject of the recommendation at all (e.g. recommending equipment replacement when no equipment audit was performed).
     * **Contradicted by findings.** The available findings directly contradict the recommendation (e.g. recommending an intervention to restore beach width when findings explicitly state no beach-width change was observed).

   **Boundary rule (when in doubt between partially_supported and unsupported):** If the recommendation's *subject* (the population, location, domain, or measurement) was studied at all in the document — even partially — it is at most partially_supported. If the *subject itself* was never measured, it is unsupported.

5. **Check each recommendation for actionability and audience.** Judge a recommendation across all its statements: it passes when any statement of it names a concrete action, and when any statement, its lead-in or its heading names who should act. Apply the exclusions above before keeping a problem. When a recommendation fails, it is reported once, on its most detailed statement.

6. **Count the distinct recommendations.** Count each recommendation once however many sections restate it, and count sub-points with the recommendation they elaborate. More than three is a problem to report.

7. **Work out the fix.** For a recommendation that is not actionable, say what is vague and propose a concrete action the findings point to; if the findings do not point to one, ask the author what action they mean. For an unclear audience, name the parties the document mentions that could act and ask the author to say which; name one only when the document makes plain it is the one meant. For too many recommendations, say which ones matter most (the ones the findings support most strongly and that bear on the document's central question) and which could be merged, cut or moved into the body.

8. **Check your suggestions.** A proposed action or actor must not go beyond what the findings support: no new number, deadline, population or causal claim the document does not establish, and no actor guessed where the document is silent.

## Reporting

Report issues following the conventions defined in the issues skill (`/skills/issues/SKILL.md`). Explain each problem in plain practical terms, what the reader cannot tell or do, never by reference to a rule or guideline. Bracket the recommendation with `start_line` and `end_line`.

**Support** — one issue per recommendation occurrence (a recommendation restated in multiple sections produces multiple issues, evaluated independently), titled with a short paraphrase of the recommendation, never with one of the fixed titles below:

- For each **supported** recommendation, emit one issue with **severity: none** — these are informational and confirm the recommendation is properly grounded.
- For each **partially_supported** recommendation, emit one issue with **severity: medium**.
- For each **unsupported** recommendation, emit one issue with **severity: high**.

**Actionability, audience and length** — separate issues, never merged into a support issue:

- **Not actionable** → one issue per recommendation, on its most detailed statement, title `"Recommendation Not Actionable"`, **severity: medium**. Quote the recommendation and say what is vague. In `suggested_action`, give the concrete action or the question for the author.
- **Unclear audience** → one issue per recommendation, on its most detailed statement, title `"Recommendation Audience Unclear"`, **severity: medium**. Quote the recommendation and name the parties the document mentions that could act. In `suggested_action`, ask the author to name who should act, proposing a party only when the document makes it plain.
- **Too many recommendations** → one issue per document, title `"Too Many Recommendations"`, **severity: low**, anchored to the first recommendation of the document's main recommendations list (the detailed list when there are several) and spanning that list. In the `description`, give the count of distinct recommendations and list them. In `suggested_action`, say which to keep and which to merge, cut or move.

Do not propose edits to the document text: which action and which actor the authors mean is theirs to decide.

### Volume and coverage

Every recommendation occurrence gets its support issue. Not-actionable and unclear-audience issues are reported for every recommendation that fails, never consolidated. The length issue is reported at most once.

## Report

In the report deliverable, state how many distinct recommendations the document makes and in which sections, how many occurrences you classified as supported, partially supported and unsupported, how many recommendations are not actionable or have an unclear audience, and whom the document's recommendations are addressed to. Keep it short.
