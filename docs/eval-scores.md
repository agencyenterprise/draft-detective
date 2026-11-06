# Eval Scores Report

Current Inspect AI eval numbers across every eval in `evals_inspectai/e2e/`.

- **Last updated:** 2026-11-06
- **Model:** `gpt-5.6-terra` on every agent
- **Total:** 29 evals · 603 runnable samples · run at epochs=3

> [!NOTE]
> All evals are **end-to-end**: they trigger the real workflow through the API,
> so the backend must be running (`uv run dev.py`). Scorer numbers are
> **accuracy** (mean over samples, `0.00`–`1.00`).
>
> Run an eval with:
> `uv run inspect eval evals_inspectai/e2e/<eval>/<eval>_e2e.py --epochs=<n>`
>
> The raw Inspect `.eval` log for each recorded run is copied under
> [`docs/evals/`](./evals/). The **Log** column opens it in the
> [hosted log viewer](https://agencyenterprise.github.io/draft-detective/evals-viewer/),
> which is rebuilt from `docs/evals/` on every push to `main`. To browse them
> locally instead, run `uv run inspect view --log-dir docs/evals`.
>
> The table below is generated from those logs; don't edit its numbers by hand.
> To record new runs, pass their logs to the generator, which copies each one
> into `docs/evals/`, points its eval's row at it, deletes the log it replaces,
> and recomputes every row, the mean and the totals:
> `uv run python -m evals_inspectai.scores_table --record <run.eval> ...`
> Run it with no arguments to regenerate from the current logs, or with
> `--check` to confirm the table matches them. A new eval needs its row added by
> hand first (number and name); the script fills in the rest.

## Results

Each eval defines its own scorers. The **Scorers** column gives how many are
deterministic and how many are model-graded, with the spread of their accuracies;
a metric no sample produced (a decoy kind the dataset lacks) is left out.
Per-scorer numbers are in the linked log, and what each scorer checks is in its
docstring under `evals_inspectai/`. **Overall avg** is the unweighted mean of the
eval's per-scorer accuracies: a rough headline, since scorers measure different
things. Model-graded scores use `openai/gpt-5.4` as the grader, except the three
review-assistant suites (18, 19 and 26), which pin `openai/gpt-5.6-terra`.

| # | Eval | Samples | Epochs | Scorers | Overall avg | Date | Log |
|---|------|--------:|-------:|---------|:-----------:|------|-----|
| 1 | `abbreviation_checker` | 36 | 3 | 22 deterministic 0.990–1.000 | **1.000** | 2026-11-05 | [`…_NMieZFGbTkbGTvEhwhomAH.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-23-41-00-00_abbreviation-checker-e2e_NMieZFGbTkbGTvEhwhomAH.eval) |
| 2 | `abbreviation_checker_report` | 10 | 3 | 20 deterministic 0.900–1.000 | **0.981** | 2026-10-13 | [`…_TzQcWxKqeESPgCnaKGeNn9.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-10-13T18-29-35-00-00_abbreviation-checker-report-e2e_TzQcWxKqeESPgCnaKGeNn9.eval) |
| 3 | `about_this_ger` | 24 | 3 | 14 deterministic 0.982–1.000 · 2 judged 0.720–0.833 | **0.969** | 2026-11-05 | [`…_UX7s2RjXqRiXXeHHdd7YDM.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_about-this-ger-e2e_UX7s2RjXqRiXXeHHdd7YDM.eval) |
| 4 | `advocacy_tone_v2` | 27 | 3 | 20 deterministic 0.981–1.000 · 2 judged 0.555–1.000 | **0.978** | 2026-11-06 | [`…_XN3f8guh9pN2AoHjYUfitf.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-06T14-42-42-00-00_advocacy-tone-v2-e2e_XN3f8guh9pN2AoHjYUfitf.eval) |
| 5 | `claim_reference_validation_v2` | 22 | 3 | 16 deterministic 0.889–1.000 · 2 judged 0.976–1.000 | **0.989** | 2026-11-05 | [`…_2owSzdqghwEb3wVicAy6ou.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_claim-reference-validation-v2-e2e_2owSzdqghwEb3wVicAy6ou.eval) |
| 6 | `document_structure` | 19 | 3 | 7 deterministic all 1.000 · 2 judged 0.870–1.000 | **0.986** | 2026-11-05 | [`…_W5cd3Efb43bWGDkshMQKNZ.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_document-structure-e2e_W5cd3Efb43bWGDkshMQKNZ.eval) |
| 7 | `figures_tables_check` | 33 | 3 | 20 deterministic 0.965–1.000 · 2 judged 0.856–0.985 | **0.988** | 2026-11-05 | [`…_mh2r6zEcG5ufgXaeRqfKT6.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T20-41-02-00-00_figures-tables-check-e2e_mh2r6zEcG5ufgXaeRqfKT6.eval) |
| 8 | `inference_validation_v2` | 32 | 3 | 18 deterministic 0.833–1.000 · 2 judged 0.986–1.000 | **0.988** | 2026-11-05 | [`…_Yst6FsforfzTAzcgeNfRn9.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_inference-validation-v2-e2e_Yst6FsforfzTAzcgeNfRn9.eval) |
| 9 | `literature_review_v2` | 12 | 3 | 13 deterministic 0.667–1.000 · 2 judged 0.930–0.947 | **0.951** | 2026-11-05 | [`…_BZV4YTLKJWdtjHZcALnPec.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_literature-review-v2-e2e_BZV4YTLKJWdtjHZcALnPec.eval) |
| 10 | `live_reports_v2` | 12 | 3 | 13 deterministic 0.977–1.000 · 2 judged 0.996–1.000 | **0.998** | 2026-11-05 | [`…_VNqJvX9tNwL4Pj3j8HNJf3.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_live-reports-v2-e2e_VNqJvX9tNwL4Pj3j8HNJf3.eval) |
| 11 | `methodological_alignment` | 10 | 3 | 7 deterministic 0.933–1.000 · 3 judged 0.894–0.989 | **0.980** | 2026-11-05 | [`…_Y3eb6CAyWRE9EhbBnt5r7a.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_methodological-alignment-e2e_Y3eb6CAyWRE9EhbBnt5r7a.eval) |
| 12 | `recommendation_check` | 15 | 3 | 18 deterministic 0.984–1.000 · 3 judged all 1.000 | **0.999** | 2026-11-05 | [`…_GrsU42YBH3jPjcntFvwj4p.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_recommendation-check-e2e_GrsU42YBH3jPjcntFvwj4p.eval) |
| 13 | `reference_downloader` | 35 | 3 | 7 deterministic 0.940–1.000 | **0.988** | 2026-09-30 | [`…_TsCQX8LiVwYLLqgvtgcARb.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-09-30T14-34-43-00-00_reference-downloader-e2e_TsCQX8LiVwYLLqgvtgcARb.eval) |
| 14 | `reference_text_extractor` | 16 | 3 | 7 deterministic 0.987–1.000 | **0.997** | 2026-09-28 | [`…_82Tfy9oyDuKFjyYuWoTE5L.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-09-28T14-01-36-00-00_reference-text-extractor-e2e_82Tfy9oyDuKFjyYuWoTE5L.eval) |
| 15 | `reference_validation_v2` | 80 | 3 | 17 deterministic 0.833–1.000 · 1 judged 0.887 | **0.959** | 2026-10-21 | [`…_myXACJhsqH24CHeyFG6r6Y.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-10-21T13-20-32-00-00_reference-validation-v2-e2e_myXACJhsqH24CHeyFG6r6Y.eval) |
| 16 | `results_extraction` | 11 | 3 | 12 deterministic 0.939–1.000 · 2 judged 0.909–0.955 | **0.981** | 2026-11-05 | [`…_QUbWNUQhXUL4hfzWwnxYcX.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_results-extraction-e2e_QUbWNUQhXUL4hfzWwnxYcX.eval) |
| 17 | `reviewer_2` | 12 | 3 | 4 deterministic all 1.000 · 6 judged 0.920–1.000 | **0.986** | 2026-09-28 | [`…_7i4fQLe3xsBqNzQ4X8AUga.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-09-28T20-52-02-00-00_reviewer-2-e2e_7i4fQLe3xsBqNzQ4X8AUga.eval) |
| 18 | `reviewer_coverage_report` | 7 | 3 | 11 deterministic 0.952–1.000 · 4 judged 0.857–0.976 · 1 identification 1.000 | **0.969** | 2026-10-14 | [`…_9Cr3gFWMtJwUGGvf4TDAA5.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-10-14T12-43-42-00-00_reviewer-coverage-report-e2e_9Cr3gFWMtJwUGGvf4TDAA5.eval) |
| 19 | `revision_planning_summary` | 6 | 3 | 6 deterministic all 1.000 · 4 judged 0.778–1.000 · 1 identification 1.000 | **0.962** | 2026-10-13 | [`…_HqFuf9T4DvM2J3zvCAqrLU.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-10-13T21-44-07-00-00_revision-planning-summary-e2e_HqFuf9T4DvM2J3zvCAqrLU.eval) |
| 20 | `active_voice` | 26 | 3 | 25 deterministic 0.833–1.000 · 3 judged 0.778–0.975 | **0.964** | 2026-11-05 | [`…_7Fmzp4Zmv4G7WKkGrV8we7.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-17-00-00_active-voice-e2e_7Fmzp4Zmv4G7WKkGrV8we7.eval) |
| 21 | `concision_precision` | 18 | 3 | 26 deterministic 0.333–1.000 · 2 judged 0.968–0.997 | **0.965** | 2026-11-05 | [`…_EYcLLMW2Cbt6kdNrcJVFf5.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-10-12-00-00_concision-precision-e2e_EYcLLMW2Cbt6kdNrcJVFf5.eval) |
| 22 | `writing_consistency` | 21 | 3 | 30 deterministic 0.989–1.000 · 1 judged 1.000 | **0.999** | 2026-11-05 | [`…_7axwyhfmrrQ5m5PM7juVS7.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_writing-consistency-e2e_7axwyhfmrrQ5m5PM7juVS7.eval) |
| 23 | `narrative_synthesis` | 15 | 3 | 21 deterministic 0.989–1.000 · 2 judged 0.994–1.000 | **0.999** | 2026-11-05 | [`…_GhCAsh3v3fDLXPQmuEwe5k.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_narrative-synthesis-e2e_GhCAsh3v3fDLXPQmuEwe5k.eval) |
| 24 | `headers_skimmability` | 16 | 3 | 18 deterministic 0.991–1.000 · 2 judged 0.943–0.961 | **0.994** | 2026-11-05 | [`…_7ckxUwaF2GREmZEheFwGfD.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-23-41-00-00_headers-skimmability-e2e_7ckxUwaF2GREmZEheFwGfD.eval) |
| 25 | `audience_fit` | 16 | 3 | 20 deterministic 0.333–1.000 · 5 judged 0.667–1.000 | **0.933** | 2026-11-05 | [`…_hjEwkU9mdQpoCwQHR8MC2z.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-10-11-00-00_audience-fit-e2e_hjEwkU9mdQpoCwQHR8MC2z.eval) |
| 26 | `reviewer_response_memos` | 6 | 3 | 8 deterministic all 1.000 · 4 judged 0.778–0.972 · 1 identification 1.000 | **0.959** | 2026-10-14 | [`…_bgdoqfEtZTCZzT6VHPtQAG.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-10-14T12-52-15-00-00_reviewer-response-memos-e2e_bgdoqfEtZTCZzT6VHPtQAG.eval) |
| 27 | `citation_consistency` | 11 | 3 | 20 deterministic 0.985–1.000 | **0.998** | 2026-11-05 | [`…_c5AMWjgHqQaNuhxmqTZxVf.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_citation-consistency-e2e_c5AMWjgHqQaNuhxmqTZxVf.eval) |
| 28 | `sentence_structure` | 12 | 3 | 22 deterministic all 1.000 · 2 judged all 1.000 | **1.000** | 2026-11-05 | [`…_ab7xQymFBfNgF4VR37o97z.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-27-16-00-00_sentence-structure-e2e_ab7xQymFBfNgF4VR37o97z.eval) |
| 29 | `structural_checks_ger` | 43 | 3 | 10 deterministic 0.985–1.000 · 5 judged 0.933–1.000 | **0.988** | 2026-11-05 | [`…_Dm7qNkDhiMmhhkCLwjxSLZ.eval`](https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/2026-11-05T19-50-22-00-00_structural-checks-ger-e2e_Dm7qNkDhiMmhhkCLwjxSLZ.eval) |
| | **Mean across all evals** | | | | **0.981** | | |
