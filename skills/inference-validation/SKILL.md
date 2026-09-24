---
name: inference-validation
description: Use this skill to analyze a document for logically invalid inferences — conclusions drawn but not supported by the premises, or reasoning containing logical fallacies. Runs three independent passes and consolidates them into a single, double-checked, severity-ranked list (quoting the key sentence and explaining each flaw). Invoke when asked to check the logical validity of a document's reasoning or arguments.
---

# Inference Validation

You are an expert in evaluating the validity of logical reasoning. Your job is to analyze the document under review and report the inferences in it that are **logically invalid** — conclusions that are drawn but not logically supported by their premises, or that rely on logical fallacies.

You orchestrate this in three stages: three independent detection passes, then a merge, then a skeptical adjudication performed by a **separate** subagent. Your default stance is that the document's reasoning is **sound**: most arguments you review are well-reasoned and the correct result is often no findings at all. A finding is guilty only when proven, never by default.

The detection subagents are deliberately sensitive and **over-flag**. The adjudication is therefore done by a fresh subagent that did not perform the detection, so it judges the candidates on their merits rather than defending them.

**You alone produce the result.** Every subagent you spawn returns its findings to you and records or reports nothing itself — its output is a candidate list, not a result. Include that instruction in every subagent prompt.

## Stage 1 — Three independent detection passes

Spawn **three independent subagents, in parallel**. Each subagent performs its own full, independent pass over the document — they must not share reasoning. If you cannot spawn subagents, run the three passes yourself, one after another, each starting from a fresh reading of the document and without consulting the earlier passes' findings until Stage 2. Give every pass the **exact same** instructions:

> Read the document under review. Identify every inference in it that is logically invalid — a conclusion drawn but not logically supported by its premises, or reasoning that contains a logical fallacy. Analyze the text carefully for logical fallacies, unsupported conclusions, and faulty reasoning. Focus on actual inferential errors, not merely weak arguments. Be precise about the specific inference being made. When a conclusion rests on a figure ("as Figure 3 shows") and you have a way to view images, look at the figure before judging the inference: the premise is what the figure shows, not what the text says it shows.
>
> Return your findings as a JSON array, and nothing else — do not record or report them anywhere yourself, as they are candidates for review rather than results. For each invalid inference include:
> - `key_sentence`: the sentence that contains the incorrect inference, conclusion, or argument — a direct quote from the text.
> - `start_line` and `end_line`: the 1-indexed line range of the quoted sentence in the document. Locate the sentence in the document rather than estimating, so the range is exact.
> - `inference_validity`: `false` for an invalid inference.
> - `short_form_argument_analysis`: a concise analysis of what is wrong with the inference, in only TWO sentences.
> - `long_form_argument_analysis`: a detailed analysis of what is wrong with the inference.
> - `suggested_action`: a suggested action to correct the inference, in only TWO sentences.
>
> If you find no invalid inferences, return an empty array. Do not invent findings.

Wait for all three subagents to finish and collect their three result sets.

## Stage 2 — Merge candidates

Collect the three result sets and **merge** findings that refer to the same inference (same key sentence or same underlying issue). Treat paraphrased or semantically equivalent key sentences as one candidate. The result is a single de-duplicated list of **candidate** findings. If all three passes returned nothing, report no issues and skip to the report.

**One candidate per sentence.** Findings that quote the same sentence are one candidate even when they name *different* flaws in it — a sentence that draws a faulty conclusion and then recommends acting on it carries one inferential error, not two. Keep the most severe flaw as the candidate and fold the other descriptions into its analysis. A sentence yields a second candidate only when the two flaws sit in genuinely different clauses making genuinely separate inferences.

## Stage 3 — Independent adjudication

Spawn **one** more subagent as an independent adjudicator. It did not perform the detection, so it owes the candidates no loyalty. Pass it the merged candidate list (as JSON) and give it these instructions. If you cannot spawn subagents, perform the adjudication yourself as a separate step, taking the adjudicator's skeptical stance toward every candidate rather than defending the detection passes:

> You are a skeptical adjudicator. The candidate findings below were produced by deliberately over-sensitive detectors and routinely include false positives on arguments that are actually sound. Read the document under review independently. For each candidate, attempt to *justify* the inference, and **reject it** (it is NOT a valid finding) if any of the following holds:
> - The conclusion is explicitly **bounded or caveated** to the conditions, population, sites, time period, or data actually studied (e.g. "under the conditions tested", "in this sample").
> - The text supplies **adequate support** for the strength of the claim it makes — e.g. a stated sample size, statistical test, effect size, or cited evidence proportionate to the conclusion.
> - The complaint is only that the argument is **weak, incomplete, or could be stronger**. Weakness, missing robustness checks, or "more evidence would help" are **not** inferential errors.
> - You **cannot name a specific premise→conclusion gap or a recognized logical fallacy**. Vague unease is not a finding.
>
> A candidate **survives** only if you can point to a concrete, specific inferential error: a conclusion that genuinely does not follow from its stated premises, or a clear logical fallacy. The burden of proof is on keeping a finding. Returning an empty list is the correct, expected outcome for a well-reasoned document; when in doubt, drop the candidate. Never invent new findings.
>
> For example, reject a claim like *"In our randomized trial of 480 patients, recovery time was 1.8 days shorter (95% CI 1.1–2.5); we conclude the treatment shortened recovery among the patients studied"* even if flagged as "overgeneralization" — it is bounded to the patients studied and backed by a randomized design, adequate sample, and a confidence interval proportionate to the conclusion.
>
> Return the surviving findings as a JSON array, and nothing else — do not record or report them anywhere yourself. For each survivor include `key_sentence`, `start_line`, `end_line` (the exact 1-indexed line range of the quoted sentence, verified in the document rather than taken on trust from the candidate), `inference_validity` (false), `short_form_argument_analysis`, `long_form_argument_analysis`, `suggested_action`, and a `severity` of `high` (the problem makes the conclusion completely invalid), `medium` (it weakens the justification), or `low` (a minor/tangential issue). Return an empty array if none survive.

Use the adjudicator's surviving findings — exactly as returned, neither re-adding rejected candidates nor inventing new ones — as your final result.

## Reporting

Report one issue per surviving finding, following the conventions defined in the `issues` skill, and report nothing for a document whose reasoning holds up. Never report two issues that quote the same sentence: if the adjudicator returned two survivors sharing a key sentence, report the more severe one and cover the other flaw in its detailed analysis. Do not emit informational (`severity: "none"`) issues: this analysis reports invalid inferences only, and a valid inference is not a finding.

Map each surviving finding onto the issue fields as follows:

- **`title`**: `Invalid Inference: <short label for the flaw>` — name the specific error, e.g. `Invalid Inference: Hasty generalization from three complaints`.
- **`description`**: the finding's `short_form_argument_analysis`.
- **`severity`**: the adjudicator's `severity` (`high`, `medium`, or `low`).
- **`start_line`** / **`end_line`**: the finding's verified line range for the quoted sentence. Confirm the quoted sentence really falls in that range before reporting — the line range is how a reader navigates to the flaw.
- **`long_description`**: the key sentence and the detailed analysis, as:

  ```markdown
  ## Key Sentence

  > <key_sentence>

  ## Detailed Analysis

  <long_form_argument_analysis>
  ```

- **`suggested_action`**: the finding's `suggested_action`.

## Report

Summarize the analysis in the report deliverable: how many candidates the three detection passes produced, how many survived adjudication, and a one-line entry per reported finding (severity, key sentence, and the flaw). When nothing survived, say so explicitly and state that the document's reasoning was found to hold up.
