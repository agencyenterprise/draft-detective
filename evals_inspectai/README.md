# Evals (Inspect AI)

LLM evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/).

## Folder Structure

```
evals_inspectai/
├── common/                            # Shared utilities (scorers, comparers, API client, solver)
└── e2e/                               # Evals that call the API end-to-end
    ├── abbreviation_checker/
    ├── about_this_ger/
    ├── advocacy_tone_v2/
    ├── claim_reference_validation_v2/
    ├── document_structure/
    ├── figures_tables_check/
    ├── inference_validation_v2/
    ├── literature_review_v2/
    ├── live_reports_v2/
    ├── methodological_alignment/
    ├── recommendation_check/
    ├── reference_downloader/
    ├── reference_text_extractor/
    ├── reference_validation_v2/
    ├── results_extraction/
    └── reviewer_2/
```

**API E2E evals** trigger workflows through HTTP, exercising the same pipeline
as real users. Their shared clients live in `evals_inspectai/common/`. The
structured abbreviation task is a separate direct-model comparison and imports
the application's checker; it is not an API end-to-end test.

## Available Evals

Each eval directory contains a task module (`<name>_e2e.py`) and its dataset. Each eval runs the corresponding workflow end-to-end through the API.

| Eval | Description |
|------|-------------|
| `e2e/abbreviation_checker` | Abbreviation compliance checks, run via the full workflow. |
| `e2e/about_this_ger` | Validates the preface / "About This" section and author biographies against publication requirements. |
| `e2e/advocacy_tone_v2` | Flags trigger words, advocacy language, and subjective tone. |
| `e2e/claim_reference_validation_v2` | Judges whether each cited source supports its claim. |
| `e2e/document_structure` | Checks that required sections are present (Document Contents). |
| `e2e/figures_tables_check` | Verifies figures and tables are titled, numbered, and cross-referenced. |
| `e2e/inference_validation_v2` | Flags invalid inferences, logical fallacies, and unsupported conclusions. |
| `e2e/literature_review_v2` | Finds relevant academic sources — supporting and conflicting — that aren't already cited. |
| `e2e/live_reports_v2` | Finds sources published after the document's date that may update or contradict its claims. |
| `e2e/methodological_alignment` | Compares the document's methodology against standard field practice (uses web search). |
| `e2e/recommendation_check` | Checks whether each recommendation is backed by the document's own findings. |
| `e2e/reference_downloader` | Searches for and downloads the full text of a reference. |
| `e2e/reference_text_extractor` | Extracts bibliographic reference entries, run via the full workflow. |
| `e2e/reference_validation_v2` | Reference Error Checker — verifies each citation exists online and matches public sources. |
| `e2e/results_extraction` | Reproducibility Check — extracts main results and classifies each by reproducibility. |
| `e2e/reviewer_2` | Produces a senior-reviewer-style critique and a devil's-advocate rebuttal. |

## Running Evals

All commands should be run from the project root.

By default, E2E evals use an existing API server (`backend=remote`), including
an already-running localhost server. They do not start local application code.
Configure the following environment variables before running:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EVAL_API_BASE_URL` | No | `http://localhost:8000` | Base URL of the API server |
| `EVAL_API_AUTH_TOKEN` | One of these | — | Pre-minted JWT Bearer token |
| `AUTH_SECRET` | One of these | — | Secret used to auto-generate a JWT |

```bash
# Start the API server first
uv run dev.py

# Run an e2e eval
uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py@abbreviation_checker_e2e
```

### Selecting the backend at eval time

Every E2E task accepts `backend` and `api_base_url` arguments. An explicit URL
overrides `EVAL_API_BASE_URL`; otherwise the default is `http://localhost:8000`.
Each solver run keeps its endpoint for all uploads, workflow starts, and polls,
so concurrent tasks cannot redirect one another.

```bash
# Evaluate an existing deployment (use its matching auth token/secret).
uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py@abbreviation_checker_e2e \
  -T backend=remote -T api_base_url=https://your-deployment.example

# Opt into running this checkout's backend. Requires application dependencies,
# database configuration, and credentials; may start the local database container.
uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py@abbreviation_checker_e2e \
  -T backend=local

# Flow configs accept the same choices through --arg.
uv run flow run evals_inspectai/flow_config/abbreviation_checker_variants.py \
  --arg backend=local --dry-run
uv run flow run evals_inspectai/flow_config/abbreviation_checker_variants.py \
  --arg backend=remote --arg api_base_url=https://your-deployment.example --dry-run
```

`backend=local` cannot be combined with an explicit `api_base_url`. It starts a
loopback API server but uses your configured database and credentials; choose
an evaluation database, not a production database. Model/provider behavior is
unchanged: remote workflows use the deployment's configuration.

For local abbreviation evals, the selected Inspect model is passed to the child
backend with `EVAL_WORKFLOW_MODEL`. Other backend agents retain their defaults;
this is not universal model routing. `run_all_evals.py` is a single-model-labeled
smoke sweep, not a comparison of backend models. Azure client settings do not
remove the OpenAI credential/embedding requirements of the full application.

The variants Flow config expects Markdown (`.md`) files and adjacent `references.json` files
under `e2e/abbreviation_checker/data/variants/{single,multi}`. It creates one task
per document and one sample per reference abbreviation. Extraction is shared
only within a document/epoch/evaluation; each of the three epochs runs a fresh extraction.
Both variant configs accept `--arg variants_dir=...`, `--arg model=provider/model`,
and `--arg epochs=3`. Resume behavior is controlled by Inspect Flow's existing logs;
use a new log directory when you want a fresh experiment, not a resumed run.

Private fixtures, derived references, logs, and local backups are ignored by Git.
The public [synthetic example](e2e/abbreviation_checker/data/README.md) provides a
reproducible starting point without publishing research documents. Pass
`-T data_dir=evals_inspectai/e2e/abbreviation_checker/data/example` for that example.

Markdown is the canonical variant input: full documents (including Markdown
tables), not short snippets. The agent receives that text directly, so repeated
evals test extraction rather than DOCX conversion, and fixture edits are readable
in Git diffs. Both variant Flow configs select only `.md`; file-based tasks prefer
Markdown over a same-stem DOCX. An explicit `filename=example.docx` still permits a
separate document-conversion test.

To migrate an existing local DOCX dataset once:

```bash
uv run python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants --migrate-docx
```

This snapshots the repository converter's Markdown without reflowing lines or
recalculating annotations. It adds `.md` filename keys to the reference JSON and
retains original DOCX files/keys for historical logs. A repeated migration refuses
to overwrite Markdown that has been edited. Review/version the `.md` fixtures and
reference JSON; the retained binary originals are not needed to run the variant
Flow configs. Migration does not stage or publish anything: publication clearance
is still required for private document content, irrespective of file format.

For future variants, edit the baseline Markdown and its matching references,
then generate Markdown directly (no DOCX involved):

```bash
uv run python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants \
  --source path/to/baseline.md --output-dir path/to/variants
```

The generator removes only the definition at its annotated source line, updates
only that occurrence's inline-definition field, preserves line numbers, and fails
before writing if an edit cannot be located unambiguously. Generation intentionally
replaces matching generated `.md` files/entries; do not use it to preserve manual
edits to generated variants. Unrelated fixtures and legacy DOCX keys are retained.

For a customized fork, run against that fork's backend with matching datasets.
Selecting a deployment does not replace generic reference answers with the
fork's expected answers. Keep private prompts and datasets in the private fork;
the common HTTP-based eval utilities can be reused in the evaluation framework.

## Structured-call abbreviation checker (no agent)

The parallel checker reads the same Markdown fixtures and reference JSON as the
agent eval, then runs one native structured model call per chunk and reconciles
the results in Python. Tables and Markdown line numbers are preserved. Explicit
legacy DOCX inputs still use the shared converter; Markdown inputs bypass it.
It runs directly in Inspect: no backend server or database is needed. The model
selected by `--model` handles every chunk, with calls and usage recorded in Inspect.
The selected provider/model must support native JSON-schema output.

```bash
uv run inspect eval \
  evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_structured.py@abbreviation_checker_structured_entries \
  --model openai/gpt-5.6-terra --epochs 3 \
  -T data_dir=evals_inspectai/e2e/abbreviation_checker/data/example \
  -T chunk_chars=8000 -T max_concurrency=4

# Every single/multi variant: one task/log per document, three epochs each.
uv run flow run evals_inspectai/flow_config/abbreviation_checker_structured_variants.py --dry-run
uv run flow run evals_inspectai/flow_config/abbreviation_checker_structured_variants.py
```

Use `-T filename=example.md` to select one document and `-T reference_path=...`
to override its adjacent `references.json`. Missing documents/references fail
before model calls. Documents with no applicable reference abbreviations cannot
use this entries task. Fixtures are not downloaded or generated automatically.

There is one sample per reference abbreviation. All abbreviations in a document
share one extraction **within an epoch only**; every new epoch makes fresh calls.
The first sample performing extraction owns the model-call events and token usage;
`metadata.structured_extraction.source_sample_id` identifies it in sibling rows.
Messages, Markdown source text, and results remain available in each sample.
Scores reuse `single_entry_scorer`: `TOTAL`, `TP`, `FP`, `TN=null`, `FN`, and nested
characterization, with pooled occurrence accuracy, precision and recall. As in
the original task, accuracy means TP/(TP+FP+FN); true negatives are undefined.
This is exact annotated-occurrence matching (Jaccard), not classification accuracy
over a fixed universe of candidates. A wrong definition counts as FP and FN.
Unknown abbreviations are charged once on the alphabetically first reference row
and identified as document-wide extras. The displayed score uses the same counts.
`TOTAL` is TP+FP+FN, not the number of abbreviations or raw source mentions.

Sample durations are not extraction timings: a row that starts after its epoch's
extraction has finished only measures scoring. Epochs can run concurrently.

`max_concurrency` limits chunk calls per document extraction; Inspect's
`--max-connections` limits requests across concurrent documents/epochs. Model
response caching and automatic request retries are disabled. Failed extractions
are not reused; Inspect sample retry runs them again. Use `-T timeout_s=1800` to
set the total conversion/extraction deadline. `chunk_chars` and `context_chars`
(default 1500 per side) are character budgets, not token budgets. The structured
variants Flow writes to `logs-structured`, separate from the agent's logs.

Scores evaluate the **post-processed workflow output**, not the raw chunk responses.
If a model invents a third occurrence where the source has only two, Python drops
that ungrounded record, retains the two valid occurrences, and records a warning
under `metadata.structured_extraction.warnings`. Unsupported definitions are cleared.
The original responses remain in the transcript for auditing. These record-level
issues do not abort the document; API failures or invalid structured responses do.

## Viewing Results

Launch the Inspect AI log viewer to browse evaluation results interactively:

```bash
uv run inspect view
```

## Resources

- [Inspect AI Documentation](https://inspect.ai-safety-institute.org.uk/docs/)
