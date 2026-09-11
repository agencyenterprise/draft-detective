# Eval Scores Report

Current Inspect AI eval numbers across every eval in `evals_inspectai/e2e/`.

- **Last updated:** 2026-09-11
- **Model:** `gpt-5.6-terra`, on every agent
- **Total:** 18 evals · 244 runnable samples · run at epochs=3

> [!IMPORTANT]
> **This is the current baseline, measured on `gpt-5.6-terra`.** On 28 Aug 2026
> every agent moved off the three-tier `gpt-5.4-mini` / `gpt-5.4` / `gpt-5.5`
> stack onto a single model. The numbers those tiers last scored are kept in
> [`docs/eval-scores-gpt-5.4-5.5.md`](./eval-scores-gpt-5.4-5.5.md) for
> comparison; they no longer describe the running system.

> [!NOTE]
> All evals are **end-to-end**: they trigger the real workflow through the API,
> so the backend must be running (`uv run dev.py`). Scorer numbers are
> **accuracy** (mean over samples, `0.00`–`1.00`), shown as `value ±stderr`.
>
> Run an eval with:
> `uv run inspect eval evals_inspectai/e2e/<eval>/<eval>_e2e.py --epochs=<n>`
>
> The raw Inspect `.eval` log for each recorded run is copied under
> [`docs/evals/`](./evals/) and linked in the **Log** column. Open one with
> `uv run inspect view --log-dir docs/evals`.

## Results

Each eval defines its own scorers. The **Scorer results** column lists every
scorer that eval runs, by its Inspect name, with the per-scorer accuracy — see
the footnotes for what each scorer checks. Expand a cell to read them; the
summary line gives the count and the spread on each side of the deterministic
/ model-graded split, which is what **Overall avg** flattens. That average is
computed over every metric in the cell, not only the ones a reader expands. **Overall avg** is the unweighted
mean of that eval's per-scorer accuracies (a rough headline number: scorers
measure different things, so it is not a rigorous aggregate). Model-graded
scores use `openai/gpt-5.4` as the grader, except the two review-assistant
suites (17 and 18), which pin `openai/gpt-5.6-terra`.

Three suites — `results_extraction` (15) and the two review-assistant ones
(17 and 18) — report one metric per check rather than a single blended score, so
every rule they enforce is listed separately. A broken rule is a defect and a
lower judged score is a trend; averaging them together hides both.

Every run below completed in full: no sample was dropped, errored or retried.

| # | Eval | Samples | Epochs | Scorer results | Overall avg | Date | Log |
|---|------|--------:|-------:|----------------|:-----------:|------|-----|
| 1 | `abbreviation_checker`[^abbr-rework] | 26 | 3 | <details><summary>2 deterministic 0.998–1.000 · 1 judged 0.968</summary>`structured_output_scorer` 0.998 ±0.001[^abbr-list]<br>`structured_output_scorer1` 1.000 ±0.000[^abbr-sect]<br>`model_graded_check` 0.968 ±0.016[^mg]</details> | **0.989** | 2026-09-11 | [`…_AnLYWQfRdG5PpYK2T6kr7g.eval`](./evals/2026-09-11T20-00-14-00-00_abbreviation-checker-e2e_AnLYWQfRdG5PpYK2T6kr7g.eval) |
| 2 | `about_this_ger` | 13 | 3 | <details><summary>2 deterministic 0.983–0.987 · 1 judged 0.936</summary>`structured_output_scorer` 0.983 ±0.017[^ger-preface]<br>`structured_output_scorer1` 0.987 ±0.013[^ger-authors]<br>`model_graded_check` 0.936 ±0.052[^mg]</details> | **0.969** | 2026-08-26 | [`…_RDABwXSRrsEUEeTGCDyPAX.eval`](./evals/2026-08-26T13-42-24-00-00_about-this-ger-e2e_RDABwXSRrsEUEeTGCDyPAX.eval) |
| 3 | `advocacy_tone_v2` | 14 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 1.000</summary>`structured_output_scorer` 1.000 ±0.000[^advv2-titles]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-08-26 | [`…_TR6MVXLpKk5aABsjrrd3BG.eval`](./evals/2026-08-26T16-59-19-00-00_advocacy-tone-v2-e2e_TR6MVXLpKk5aABsjrrd3BG.eval) |
| 4 | `claim_reference_validation_v2` | 7 | 3 | <details><summary>2 deterministic all 1.000 · 1 judged 1.000</summary>`citation_alignment_match` 1.000 ±0.000[^cr-align]<br>`citation_count_match` 1.000 ±0.000[^cr-count]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-08-26 | [`…_P6c7epQuUUuYnrhLJszKwY.eval`](./evals/2026-08-26T16-55-04-00-00_claim-reference-validation-v2-e2e_P6c7epQuUUuYnrhLJszKwY.eval) |
| 5 | `document_structure` | 5 | 3 | <details><summary>1 deterministic 0.933 · 1 judged 0.800</summary>`structured_output_scorer` 0.933 ±0.067[^issue-titles]<br>`model_graded_check` 0.800 ±0.200[^mg]</details> | **0.867** | 2026-08-28 | [`…_gVQDPn5E5ru4cJJdYpuGBk.eval`](./evals/2026-08-28T18-11-07-00-00_document-structure-e2e_gVQDPn5E5ru4cJJdYpuGBk.eval) |
| 6 | `figures_tables_check`[^fig-images] | 22 | 3 | <details><summary>2 deterministic 0.818–1.000 · 1 judged 0.939</summary>`structured_output_scorer` 0.818 ±0.054[^issue-titles]<br>`model_graded_check` 0.939 ±0.043[^mg]<br>`tool_called` 1.000[^tool-called]</details> | **0.919** | 2026-09-03 | [`…_CfvWthBA2pjPkRAvo9iovz.eval`](./evals/2026-09-03T20-47-36-00-00_figures-tables-check-e2e_CfvWthBA2pjPkRAvo9iovz.eval) |
| 7 | `inference_validation_v2`[^fig-images] | 8 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 1.000</summary>`structured_output_scorer` 1.000 ±0.000[^inf-count]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-09-03 | [`…_aRbGdAo9YpNAWYAer7kNVv.eval`](./evals/2026-09-03T20-45-55-00-00_inference-validation-v2-e2e_aRbGdAo9YpNAWYAer7kNVv.eval) |
| 8 | `literature_review_v2` | 4 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 0.958</summary>`structured_output_scorer` 1.000 ±0.000[^score-structure]<br>`model_graded_check` 0.958 ±0.042[^mg]</details> | **0.979** | 2026-08-26 | [`…_jkRHzj4yivsY66vtVbCo4a.eval`](./evals/2026-08-26T16-39-44-00-00_literature-review-v2-e2e_jkRHzj4yivsY66vtVbCo4a.eval) |
| 9 | `live_reports_v2` | 3 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 1.000</summary>`structured_output_scorer` 1.000 ±0.000[^score-structure]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-08-26 | [`…_B8DravaK7UWAGrngodBEco.eval`](./evals/2026-08-26T16-36-22-00-00_live-reports-v2-e2e_B8DravaK7UWAGrngodBEco.eval) |
| 10 | `methodological_alignment` | 2 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 1.000</summary>`structured_output_scorer` 1.000 ±0.000[^meth-structure]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-09-03 | [`…_E6GDRmwbe9Rc4xHe5tgPRH.eval`](./evals/2026-09-03T16-20-12-00-00_methodological-alignment-e2e_E6GDRmwbe9Rc4xHe5tgPRH.eval) |
| 11 | `recommendation_check`[^fig-images] | 8 | 3 | <details><summary>2 deterministic 0.986–1.000 · 1 judged 0.896</summary>`structured_output_scorer` 0.986 ±0.007[^rec-severity]<br>`model_graded_check` 0.896 ±0.054[^mg]<br>`tool_called` 1.000[^tool-called]</details> | **0.961** | 2026-09-03 | [`…_ZTUHrzow367DsJUyXeTFPg.eval`](./evals/2026-09-03T20-40-25-00-00_recommendation-check-e2e_ZTUHrzow367DsJUyXeTFPg.eval) |
| 12 | `reference_downloader` | 31 | 3 | <details><summary>1 deterministic 0.849</summary>`structured_output_scorer` 0.849 ±0.060[^refdl-conclusion]</details> | **0.849** | 2026-08-28 | [`…_YHhh9v2dMmLZVkBdoGLaNi.eval`](./evals/2026-08-28T18-24-42-00-00_reference-downloader-e2e_YHhh9v2dMmLZVkBdoGLaNi.eval) |
| 13 | `reference_text_extractor` | 7 | 3 | <details><summary>1 deterministic 0.878</summary>`structured_output_scorer` 0.878 ±0.084[^refext-refs]</details> | **0.878** | 2026-08-28 | [`…_EcCoBLxfCqnUGhVwdMwCzR.eval`](./evals/2026-08-28T18-12-45-00-00_reference-text-extractor-e2e_EcCoBLxfCqnUGhVwdMwCzR.eval) |
| 14 | `reference_validation_v2` | 70 | 3 | <details><summary>1 deterministic 0.814 · 1 judged 0.824</summary>`structured_output_scorer` 0.814 ±0.044[^refval-result]<br>`model_graded_check` 0.824 ±0.033[^mg]</details> | **0.819** | 2026-08-26 | [`…_LVNQd5h6f5bUWnD2eYogUb.eval`](./evals/2026-08-26T17-17-18-00-00_reference-validation-v2-e2e_LVNQd5h6f5bUWnD2eYogUb.eval) |
| 15 | `results_extraction`[^res-devsplit][^fig-images] | 11 | 3 | <details><summary>12 deterministic 0.968–1.000 · 2 judged 0.879–0.970</summary>`report` 1.000 ±0.000<br>`inventory_table` 1.000 ±0.000<br>`result_count` 1.000 ±0.000<br>`labels` 1.000 ±0.000<br>`severity_split` 1.000 ±0.000<br>`line_ranges` 1.000 ±0.000<br>`no_duplicates` 1.000 ±0.000[^res-shape]<br>`completeness` 1.000 ±0.000<br>`class_accuracy` 0.968 ±0.025<br>`no_extras` 0.978 ±0.016<br>`severity_ordering` 1.000 ±0.000[^res-truth]<br>`classification_grounded` 0.970 ±0.020<br>`sample_expectations` 0.879 ±0.055[^res-rubric]<br>`tool_called` 1.000[^tool-called]</details> | **0.985** | 2026-09-03 | [`…_iMzDaGm4SpnSJPpWfTAJM3.eval`](./evals/2026-09-03T20-40-30-00-00_results-extraction-e2e_iMzDaGm4SpnSJPpWfTAJM3.eval) |
| 16 | `reviewer_2`[^fig-images] | 3 | 3 | <details><summary>1 deterministic 1.000 · 1 judged 1.000</summary>`structured_output_scorer` 1.000 ±0.000[^rev-produced]<br>`model_graded_check` 1.000 ±0.000[^mg]</details> | **1.000** | 2026-09-03 | [`…_F9nMo3w7HqpfRxYJgbhm7F.eval`](./evals/2026-09-03T20-40-28-00-00_reviewer-2-e2e_F9nMo3w7HqpfRxYJgbhm7F.eval) |
| 17 | `reviewer_coverage_report` | 5 | 3 | <details><summary>9 deterministic all 1.000 · 4 judged 0.800–0.967</summary>`verbatim` 1.000 ±0.000<br>`quoted` 1.000 ±0.000<br>`id_scheme` 1.000 ±0.000<br>`self_contained` 1.000 ±0.000<br>`two_part_layout` 1.000 ±0.000<br>`voice` 1.000 ±0.000[^ra-structure]<br>`verdict_table` 1.000 ±0.000<br>`verdict_vocabulary` 1.000 ±0.000<br>`recommendation` 1.000 ±0.000[^rcr-bookkeeping]<br>`verdicts_correct` 0.800 ±0.062<br>`part1_is_decision_grade` 0.900 ±0.041<br>`evidence_and_location` 0.967 ±0.033<br>`scenario_trap` 0.800 ±0.133[^rcr-rubric]</details> | **0.959** | 2026-08-26 | [`…_nnzWgW7JK6KsFFqorqCSck.eval`](./evals/2026-08-26T15-01-34-00-00_reviewer-coverage-report-e2e_nnzWgW7JK6KsFFqorqCSck.eval) |
| 18 | `revision_planning_summary` | 5 | 3 | <details><summary>6 deterministic all 1.000 · 4 judged 0.800–1.000</summary>`verbatim` 1.000 ±0.000<br>`quoted` 1.000 ±0.000<br>`id_scheme` 1.000 ±0.000<br>`self_contained` 1.000 ±0.000<br>`two_part_layout` 1.000 ±0.000<br>`voice` 1.000 ±0.000[^ra-structure]<br>`locations_by_content` 0.967 ±0.033<br>`part1_triage` 0.800 ±0.062<br>`planning_notes` 1.000 ±0.000<br>`scenario_trap` 0.800 ±0.097[^rps-rubric]</details> | **0.957** | 2026-08-26 | [`…_iUkias5YSUsBuY2EoRoKqm.eval`](./evals/2026-08-26T15-11-52-00-00_revision-planning-summary-e2e_iUkias5YSUsBuY2EoRoKqm.eval) |
| | **Mean across all evals** | | | | **0.952** | | |

## What the model switch changed

Against the last gpt-5.4 / gpt-5.5 figures. Six evals are unchanged, four
improved and eight fell, for a suite mean **0.009 lower**. Only one movement is
large enough to matter on its own.

| Eval | gpt-5.4 / gpt-5.5 | gpt-5.6-terra | Δ |
|------|------------------:|--------------:|--:|
| `abbreviation_checker` | 0.993 | 0.995 | +0.002 |
| `about_this_ger` | 0.983 | 0.969 | -0.014 |
| `advocacy_tone_v2` | 0.994 | 1.000 | +0.006 |
| `claim_reference_validation_v2` | 1.000 | 1.000 | — |
| `document_structure` | 0.867 | 0.867 | — |
| `figures_tables_check` | 0.864 | 0.780 | -0.084 |
| `inference_validation_v2` | 1.000 | 1.000 | — |
| `literature_review_v2` | 0.944 | 0.979 | +0.035 |
| `live_reports_v2` | 1.000 | 1.000 | — |
| `methodological_alignment` | 0.958 | 1.000 | +0.042 |
| `recommendation_check` | 0.955 | 0.953 | -0.002 |
| `reference_downloader` | 0.903 | 0.849 | -0.054 |
| `reference_text_extractor` | 0.922 | 0.878 | -0.044 |
| `reference_validation_v2` | 0.848 | 0.819 | -0.029 |
| `results_extraction` | 1.000 | 1.000 | — |
| `reviewer_2` | 1.000 | 1.000 | — |
| `reviewer_coverage_report` | 0.972 | 0.959 | -0.013 |
| `revision_planning_summary` | 0.967 | 0.957 | -0.010 |
| **Mean across all evals** | **0.954** | **0.945** | **-0.009** |

Four things worth knowing before reading that table:

- **`results_extraction` is no longer comparable, in either direction.** Both
  columns read 1.000 because that is what its old scorers measured: 2 samples,
  every expected result not-reproducible, and a deterministic check that counted
  results and validated a class string. The eval was rebuilt on 31 Aug — 10
  samples, ground-truth inventories, 13 per-check metrics — and read 0.977 that
  day, pooled over three invocations; on 3 Sep, with a chart sample and the
  `tool_called` check added (11 samples, 14 metrics), it reads 0.985. The two
  numbers measure different things and differencing them means nothing. This is
  also why the suite mean in the table above (0.945) and the one in the Results
  table (0.952) differ: the table above is a frozen record of the model switch,
  the Results table is current.
- **`figures_tables_check` is the one real regression.** It fell 8.4 points, on
  both of its scorers, and it is the only movement here that was measured twice
  and held both times — 0.798 on 26 Aug and 0.780 on 28 Aug. The deterministic
  issue-title match moving means terra flags different figures and tables, not
  that a grader changed its mind. This is a known cost of the switch, not noise.
  On 3 Sep, with the image-viewing tool bound and three figure samples added,
  the suite read 0.919; the nineteen original samples alone moved from
  0.710 to 0.789 on the title match and 0.851 to 0.930 judged. Read that as
  recovery, not as the switch cost reversing: the skill text was clarified
  along the way (see [^fig-images]).
- **The small evals swing.** `document_structure` read 0.778 on 26 Aug and
  0.867 — exactly its old figure — on 28 Aug, with nothing changed between the
  runs. At 15 runs with a judged scorer carrying ±0.200, single readings on the
  sub-20-run evals should not be read as trends in either direction.
- **The review-assistant suites now grade themselves.** `reviewer_coverage_report`
  and `revision_planning_summary` pin `openai/gpt-5.6-terra` as their judge,
  which is now also the model under test. Their judged criteria should be read
  with that in mind; their deterministic rules, all of which still pass at 1.000,
  are unaffected.

## Scorer reference

[^mg]: `model_graded_check` — an LLM grader compares the workflow's full output against the target answer, with partial credit. Some evals grade against a `target_answer` in sample metadata; the mechanism is otherwise identical across evals.
[^abbr-rework]: `abbreviation_checker` · re-baselined on 11 Sep 2026 after the workflow was reworked to fix silent truncation on long documents: the agent now paginates `/main.md` in 200-line chunks and records occurrences through a `record_abbreviations` tool instead of returning the whole catalogue in one structured response, and each compliance rule reports once per abbreviation rather than once per occurrence (`severity=none` informational entries are no longer emitted). The scorers and the dataset are unchanged, so this number is comparable with the 0.995 it replaces; the 0.006 drop sits inside `model_graded_check`'s stderr. The eval's 26 samples are all short documents, which is why they barely move — the rework shows up on long ones: a 111-page fixture went from 113 recorded occurrences to 975, and from 358 medium plus 1,396 none-severity issues to 40. The **0.995** listed for this eval in *What the model switch changed* below is the pre-rework figure and is left as recorded, since that table documents the 28 Aug model migration rather than the current baseline.
[^abbr-list]: `abbreviation_checker` · deterministic match of the extracted abbreviations list against the target (inline definition, line span, section definition, ignored flag).
[^abbr-sect]: `abbreviation_checker` · deterministic check that the "Abbreviations section found" boolean matches the target.
[^ger-preface]: `about_this_ger` · deterministic match of the flagged preface / "About This" issue titles against the target.
[^ger-authors]: `about_this_ger` · deterministic match of the flagged author-biography issue titles against the target.
[^advv2-titles]: `advocacy_tone_v2` · deterministic match of the count of flagged issue titles against the target.
[^cr-align]: `claim_reference_validation_v2` · checks each citation's support label aligns with the target (supported / partially / unsupported / unverifiable).
[^cr-count]: `claim_reference_validation_v2` · checks the number of citations found matches the target.
[^issue-titles]: `document_structure` and `figures_tables_check` · deterministic match of the detected issue titles against the target.
[^tool-called]: `figures_tables_check`, `recommendation_check` and `results_extraction` · behavioural check, recorded on 3 Sep: whether the run's transcript shows the agent calling `view_image` on a sample whose document embeds a figure. It is a plain rate over the figure samples (the metric is `applicable_mean`, so it carries no ±stderr and text-only samples are left out rather than counted as passes), and it sits next to the outcome scorers because a sample built so the right answer is only reachable from the image can still be passed by a lucky guess. `inference_validation_v2` and `reviewer_2` cannot carry it: the former delegates the reading to sub-agents whose transcripts are not persisted, the latter's state holds the two documents and no transcript. Their figure samples are built so the outcome scorers only pass if the chart was read.
[^fig-images]: Figure samples, added 3 Sep across five suites (3 in `figures_tables_check`, 2 each in `inference_validation_v2` and `recommendation_check`, 1 each in `results_extraction` and `reviewer_2`). Each document embeds a PNG chart, drawn deterministically by `evals_inspectai/files/figures/generate_fixtures.py` and inlined as a data URI at upload, that carries information the text does not: a logo that is not a figure, a caption rendered inside the image, an author's placeholder box where a chart should be, tercile means that exist only in a bar chart, a pair of documents with identical text whose charts make the same claim true or false, and a sub-point effect drawn on a truncated axis. Every figure sample scored 1.000 on every outcome scorer in every epoch of the recorded runs. Two findings from building them are worth keeping: the `figures-tables-check` skill's first draft of its image guidance made the agent report every table-rendered figure in the text-only samples as missing (0.620 / 0.674 on a run that is not recorded here), fixed by stating that a figure whose content is a table or text under its caption is present; and the inference pair originally split its false premise and false conclusion across two sentences, which the skill's one-candidate-per-sentence rule correctly counted as two findings, fixed by making them one sentence.
[^inf-count]: `inference_validation_v2` · deterministic match of the count of reported invalid inferences against the target. An informational (`none`) issue fails the sample outright rather than counting towards the total: this assessment reports invalid inferences only, so sound reasoning is reported as nothing at all.
[^score-structure]: `literature_review_v2` and `live_reports_v2` · structural checks averaged into a `[0,1]` score (result present with non-empty report, issue count within the expected band, sane line ranges, citation-like detail when recommendations are expected). Exact sources aren't asserted because web search is non-deterministic.
[^meth-structure]: `methodological_alignment` · structural checks averaged into a `[0,1]` score, recorded on 3 Sep after the workflow moved onto the simple deep agent: a non-empty report carrying the skill's five sections (extracted methodology, field overview, alignment, rigor and risks, suggestions), at least one web citation as a markdown link, at least the sample's minimum number of issues, sane line ranges on every issue, and no informational (`none`) issues. The comparison prose is free-form and the field baseline comes from live web search, so exact wording and sources aren't asserted. The 26 Aug reading this replaced checked the old structured output for a reproducibility class and an alignment section, so only the judged score is comparable across the two; it read 1.000 both times.
[^rec-severity]: `recommendation_check` · deterministic match of the counts of recommendations by severity against the target.
[^refdl-conclusion]: `reference_downloader` · deterministic match of the final download conclusion against the target.
[^refext-refs]: `reference_text_extractor` · deterministic match of the extracted bibliographic references against the target.
[^refval-result]: `reference_validation_v2` · deterministic match of the final validation result label against the target.
[^res-devsplit]: `results_extraction` · **read this as a dev-split figure, not an unbiased estimate.** Ten of these eleven samples were built and then tuned against this workflow across roughly fifteen runs on 31 Aug: three documents, the skill's class-selection guidance, the judged criteria and the workflow's reasoning effort were all edited while these same samples were being scored. Eight of the ten documents are synthetic. Two independent audits found ground-truth defects that had been scoring the workflow *down for being right* — an engineering estimate that did not follow from its own coefficients, a reservoir yield its own inflow record could not supply, a matching variable the document never stated, and paid-access sources cited in a fixture whose expected class requires openly available ones. Each is fixed, and `tests/unit/evals/test_reproducibility_dataset_arithmetic.py` plus `evals_inspectai/e2e/results_extraction/verify_reservoir_yields.py` now re-derive the numbers behind every fully-reproducible expectation. But a dataset repaired wherever the system under test objected to it is a dataset biased towards that system: the gain from 0.899 to 0.977 across this day is mostly eval error being removed, not the workflow improving, and nothing here has been measured on samples the workflow has never influenced. Treat a single reading here as approximate. The ten-sample configuration was run four times and `class_accuracy` came out 0.879, 0.922, 0.942 and 0.992; the recorded 3 Sep run, with the chart sample added, read 0.968, inside that band, so read the row as an indication rather than a ceiling. On ten samples a five-point swing between runs is ordinary, and a regression has to clear that before it means anything. Held-out samples are the outstanding work — blind-authored documents, one adversarial case that falsely claims reproducibility, and one full-length real report. Until those exist, treat this eval as a tripwire for large regressions rather than a quality score.
[^res-shape]: `results_extraction` · seven deterministic checks on the shape of the delivery: a substantive markdown report, an inventory table in it (found by the reproducibility column its header names, not by being the widest table in the report) with at least a row per reported result, at least as many results as the dataset declares, a recognised reproducibility label in every issue title, the severity split the skill mandates (anything reproducible is informational `none`; only not-reproducible carries a real severity), line ranges that land inside the document, and no result reported twice. None of these say whether a classification is *right*.
[^res-truth]: `results_extraction` · four deterministic checks against the dataset's own ground-truth inventory, which names every result each document presents together with the class it should be given and how much the document rests on it: whether every expected result was found, the fraction given the right reproducibility class, whether anything was reported that the document does not present as a result, and whether the severities of the non-reproducible results are ordered by importance. Which of low/medium/high a result earns is the agent's judgement, so only the ordering is asserted, not the level.
[^res-rubric]: `results_extraction` · two judged criteria, each graded three times with the median taken, because single grader calls disagreed with themselves across repeats of an unchanged output. `classification_grounded` asks only whether each rationale names the ingredients present or missing and how a reader would obtain them; it is given the four class definitions and the list of absences the skill says are *not* deficiencies, since without them the grader marked down rationales for correctly declining to treat an unrendered figure or a fixed-seed simulation as a gap. `sample_expectations` is the dataset's own per-sample rubric. Both use a requirement-shaped prompt rather than Inspect's model-graded-fact template, which asks whether the submission *contains* the expert answer and misgrades a criterion that states a property the output must have.
[^ra-structure]: `reviewer_coverage_report` and `revision_planning_summary` · the rules the `review-assistant` skill states outright, checked deterministically against the report's HTML: every reviewer memo reproduced verbatim, that reproduced text sitting inside a marked quote, a valid per-reviewer point-ID scheme numbered from 1 with no gaps, a self-contained document (no external stylesheets, fonts, scripts or images, and no `<script>`), a visible two-part split with a short first part, and none of the generic-assistant tells the `voice-and-tone` skill bans, counted only outside quotes so the reviewer's own punctuation is not held against it.
[^rcr-bookkeeping]: `reviewer_coverage_report` · the arithmetic of the summary table, checked deterministically: all four verdict categories present including the ones that scored zero, every point accounted for exactly once and at one granularity with the stated counts matching the IDs listed, the four-point scale actually used in Part 2 rather than only declared in the table header, and Part 1 stating the sign-off decision outright. Whether an individual verdict is *right* is judged separately.
[^rcr-rubric]: `reviewer_coverage_report` · four judged criteria, each graded in its own call so one weak area cannot colour the rest: each point's verdict is correct against both drafts, Part 1 is decision-grade for a QAM, each verdict cites evidence and a location, and a per-scenario trap criterion for the specific failure that scenario is built to provoke.
[^rps-rubric]: `revision_planning_summary` · four judged criteria, graded one call each: reviewer points located by content rather than by numbers the revision will move, Part 1 triaging substantial asks apart from quick fixes, a planning note under each quoted point carrying scope and location and a suggestion, and a per-scenario trap criterion.
[^rev-produced]: `reviewer_2` · shape check that both the peer review and the rebuttal were produced and are substantive (the model-graded scorer judges whether they cover strengths, weaknesses, and next steps).
