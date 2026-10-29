# Evals (Inspect AI)

LLM evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/).

## Folder Structure

```
evals_inspectai/
├── common/                            # Shared utilities (scorers, issue inventory and checks, API client, solver)
├── e2e/                               # Evals that call the API end-to-end
│   ├── abbreviation_checker/
│   ├── about_this_ger/
│   ├── active_voice/
│   ├── advocacy_tone_v2/
│   ├── audience_fit/
│   ├── citation_consistency/
│   ├── claim_reference_validation_v2/
│   ├── concision_precision/
│   ├── document_structure/
│   ├── figures_tables_check/
│   ├── headers_skimmability/
│   ├── inference_validation_v2/
│   ├── literature_review_v2/
│   ├── live_reports_v2/
│   ├── methodological_alignment/
│   ├── narrative_synthesis/
│   ├── recommendation_check/
│   ├── reference_downloader/
│   ├── reference_text_extractor/
│   ├── reference_validation_v2/
│   ├── sentence_structure/
│   ├── results_extraction/
│   ├── reviewer_2/
│   ├── reviewer_coverage_report/
│   ├── reviewer_response_memos/
│   ├── revision_planning_summary/
│   └── writing_consistency/
└── files/                             # Shared fixtures (source documents, figures, peer-review scenarios)
```

**E2E evals** trigger workflows through the HTTP API, exercising the full
pipeline exactly as real users do. They only depend on
`evals_inspectai/common/`, making them portable to a standalone repository in
the future.

## Available Evals

Each eval directory contains a task module (`<name>_e2e.py`) and its dataset. Each eval runs the corresponding workflow end-to-end through the API.

| Eval | Description |
|------|-------------|
| `e2e/abbreviation_checker` | Abbreviation compliance checks, run via the full workflow. A second task, `abbreviation_checker_report_e2e.py`, runs the same checks on a full-length report and nine variants of it with definitions removed; it is kept separate because its samples are long. |
| `e2e/about_this_ger` | Validates the preface / "About This" section and author biographies against publication requirements. |
| `e2e/active_voice` | Flags passive voice and sentences that hide who acts, with active rewrites. `active_voice_judge_calibration.py` checks the edit judge against human-labelled pairs; it calls no API, only the grader. |
| `e2e/advocacy_tone_v2` | Flags trigger words, advocacy language, and subjective tone. |
| `e2e/audience_fit` | Checks that the document names a specific audience and that its vocabulary suits it. |
| `e2e/citation_consistency` | Checks in-text and note citations against the document's own reference list and house citation style, with no web access. |
| `e2e/claim_reference_validation_v2` | Judges whether each cited source supports its claim. |
| `e2e/concision_precision` | Flags wordy, run-on, filler and imprecise sentences, with tighter rewrites. |
| `e2e/document_structure` | Checks that required sections are present (Document Contents). |
| `e2e/figures_tables_check` | Verifies figures and tables are titled, numbered, and cross-referenced. |
| `e2e/headers_skimmability` | Checks the bottom line up front, headers that state each section's point, bold lead sentences and the key findings box. |
| `e2e/inference_validation_v2` | Flags invalid inferences, logical fallacies, and unsupported conclusions. |
| `e2e/literature_review_v2` | Finds relevant academic sources — supporting and conflicting — that aren't already cited. |
| `e2e/live_reports_v2` | Finds sources published after the document's date that may update or contradict its claims. |
| `e2e/methodological_alignment` | Compares the document's methodology against standard field practice (uses web search). |
| `e2e/narrative_synthesis` | Reviews the argument's order, framing questions, data dumps and restated points. |
| `e2e/recommendation_check` | Checks whether each recommendation is backed by the document's own findings. |
| `e2e/reference_downloader` | Searches for and downloads the full text of a reference. |
| `e2e/reference_text_extractor` | Extracts bibliographic reference entries, run via the full workflow. |
| `e2e/reference_validation_v2` | Reference Error Checker — verifies each citation exists online and matches public sources. |
| `e2e/sentence_structure` | Flags incomplete sentences, broken shared constructions, faulty parallelism and indirect summary sentences, with restructured rewrites. |
| `e2e/results_extraction` | Reproducibility Check — extracts main results and classifies each by reproducibility. |
| `e2e/reviewer_2` | Produces a senior-reviewer-style critique and a devil's-advocate rebuttal. |
| `e2e/reviewer_coverage_report` | Review Assistant: the coverage report on how a revised draft answers each reviewer point. |
| `e2e/reviewer_response_memos` | Review Assistant: the author's response memo to each reviewer. |
| `e2e/revision_planning_summary` | Review Assistant: the revision-planning summary of a draft's reviewer memos. |
| `e2e/writing_consistency` | Checks terms, spellings, tenses, tone and house-style compounds are consistent across the document. |

## Running Evals

All commands should be run from the project root.

E2E evals require a running API server. Configure the following environment
variables before running:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EVAL_API_BASE_URL` | No | `http://localhost:8000` | Base URL of the API server |
| `EVAL_API_AUTH_TOKEN` | One of these | — | Pre-minted JWT Bearer token |
| `AUTH_SECRET` | One of these | — | Secret used to auto-generate a JWT |
| `EVAL_USER_EMAIL` | No | `eval@draft-detective.local` | Email in the auto-generated JWT: the user the eval's projects belong to |
| `EVAL_USER_NAME` | No | `E2E Eval Runner` | Name in the auto-generated JWT |

```bash
# Start the API server first
uv run dev.py

# Run an e2e eval
uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py
```

### Choosing the workflow model

Without `--model`, every agent runs on its own model. `--model` switches all of
the run's agents to another one, and the log records it as the eval's model:

```bash
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py \
  --model openai/gpt-5.6-sol --model-role grader=openai/gpt-5.4
```

The API server must be started with `ALLOW_WORKFLOW_MODEL_OVERRIDE=true`; any
model LangChain can build is then accepted (Inspect's `google/...` is sent as
`google_genai:...`). Each agent's reasoning effort is passed in the provider's
own terms: OpenAI's `reasoning`, and adaptive thinking plus `effort` on Claude,
which needs a Claude 4.6 or later model. A sample fails if its run was not
served by the requested model.
Graders are unaffected: they use the `grader` role, or their own default.

## Viewing Results

Launch the Inspect AI log viewer to browse evaluation results interactively:

```bash
uv run inspect view
```

## Resources

- [Inspect AI Documentation](https://inspect.ai-safety-institute.org.uk/docs/)
