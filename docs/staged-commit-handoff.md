# Developer handoff: abbreviation evaluation

Updated September 22, 2026 after the pre-PR audit. This describes the proposed
working-tree changes against `HEAD`, including the structured checker. No commit,
push, deployment, database migration, or paid evaluation was performed by the audit.

## Scope and review order

1. **Fixture selection and scoring:** `evals_inspectai/e2e/abbreviation_checker/`.
   Full-document Markdown inputs, one sample per reference abbreviation, strict
   fixture validation, deterministic occurrence comparison, and variant generation.
2. **API evaluation plumbing:** `evals_inspectai/common/` and the E2E task arguments.
   Explicit endpoint propagation; opt-in local backend; successful extraction sharing
   within an evaluation/document/epoch. Existing remote execution remains the default.
3. **Structured alternative:** `lib/agents/abbreviation_checker_structured.py` and
   its Inspect task. Opt-in direct structured calls, not a replacement production workflow.
4. **Small production changes:** abbreviation prompt and glossary backfill; optional
   MCP startup; explicit local abbreviation-model override and Azure client settings.
5. **Flow, documentation, tests:** configurable variant sweeps and a public synthetic
   example. `inspect-flow` is the only added direct dependency.

The separate [model-routing proposal](model-routing-proposal.md) is design-only.
There are no frontend, mirror-sync, deployment, or schema changes in this work.

## Evaluation contract

An entries task creates rows from the reference JSON **before** inference. Each
document is extracted once per epoch; sibling abbreviation rows score the same
epoch's output. Three epochs mean three independent successful extractions, plus
any retries. Epochs may overlap. Near-zero sibling sample durations measure scoring,
not extraction time.

The API cache is task-local and keyed by evaluation ID, endpoint, workflow, resolved
document path, and epoch. It stores only successful results, and messages are copied
per row. Reusing a Task in a new evaluation cannot reuse its old extraction. The
structured task also isolates by model; native model caching and SDK retries are off.
Flow may separately resume completed tasks from existing logs: choose a fresh log
directory for a fresh experiment.

Each score has `TOTAL`, `TP`, `FP`, `TN`, `FN`, and nested `characterization`:

- TP: exact annotated-occurrence matches, including definitions and line anchors.
- FP: unmatched predictions, including incorrect annotations.
- FN: unmatched reference annotations. A field mismatch contributes FP **and** FN.
- TN: undefined (`null`), since no finite negative-candidate universe is enumerated.
- TOTAL: TP+FP+FN, **not** document abbreviation count.
- Displayed score and pooled occurrence accuracy: TP/TOTAL (Jaccard).
- Precision: TP/(TP+FP); recall: TP/(TP+FN).

Unknown abbreviations are charged once on the alphabetically first reference row,
explicitly labeled as document-wide extras. This keeps one row per expected
abbreviation and avoids multiplying false positives. Full-dataset pooled metrics
are preferable to interpreting that first row as purely abbreviation-specific;
filtering it out also excludes those extras. Same-line occurrences are matched
one-to-one; occurrence ordinals are only a tiebreaker after annotation similarity.

The older document-level `abbreviation_list` scorer remains reference recall with
extra predictions reported separately. `analyze_logs.py` supports that older scorer,
not the entries scorer. Historical scores are not directly comparable to corrected
entries scores: the audit fixed inconsistent displayed scores and mismatch counts.

## Structured checker

Markdown is read verbatim. Explicit DOCX inputs use the existing MarkItDown converter.
Disjoint chunks have bounded surrounding context. One native JSON-schema call per
chunk identifies occurrences/definitions; deterministic Python anchors mentions,
merges plural forms, assigns ordinals, and propagates glossary definitions.

No agent loop, tools, LLM repair pass, or cross-epoch response reuse. Invalid records
are discarded with warnings; unsupported definitions are cleared. API/schema failures
fail the extraction rather than produce partial success. Raw responses remain logged.
Scores measure this post-processed output, not raw model predictions. Identification
and local definition association remain model-dependent; grounding does not guarantee
recall or semantic correctness.

## Backend behavior and limits

- Tasks accept `backend=remote|local` and `api_base_url`. Explicit URL overrides
  `EVAL_API_BASE_URL`. Local mode plus an explicit URL is rejected.
- One upload/start/poll implementation is used by the generic API agents. Multi-step
  helpers forward the same URL throughout; no process-global routing mutation.
- Local mode starts a loopback Uvicorn child with MCP disabled. Startup errors and
  cancellation clean up the child/state. Compose and dotenv use the configured repo
  directory; database probes do not block the event loop; Compose startup is bounded.
- A local server **still writes to its configured database and file store**, which
  may be remote. Use an evaluation environment. Created projects are not auto-deleted.
- Local abbreviation runs preserve Inspect's provider/model name. Most other agents
  still use fixed models; remote workflows use deployment configuration. The all-eval
  Flow is a 19-workflow smoke sweep, not a multi-model backend comparison.
- Azure settings support explicitly selected clients, not an Azure-only application.
  OpenAI credential and embedding checks remain intact. Arbitrary-provider parameter
  compatibility and universal routing remain separate work.
- MCP remains enabled by default; public deployment authentication is unchanged.

The audit removed an incomplete Langfuse API field/link and the Azure-key bypass of
OpenAI preflight. Neither should be presented as completed backend support.

## Public/private boundary

Only `data/README.md` and `data/example/` belong to this PR. The example is synthetic,
with table mentions and a glossary. Private source documents, Markdown, derived
references, results, Flow metadata, and local backups are ignored. Do not force-add
them. Changing file format does not grant publication clearance.

Redundant DOCX fixtures and the loose extraction JSON were moved to the ignored
`.local/pr-audit-backup/` directory, not destroyed. Historical DOCX reference keys
remain in local references for old logs. The previous staged patch and handoff are
also backed up there. No private fixture was sent to an external service by the audit.

Keep customized prompts and matching datasets in the private fork. This PR changes
neither its synchronization script nor the evaluation-framework repository.

## Reproduce without private fixtures

```bash
# Fixture generation is local and deterministic; no LLM or backend call.
uv run python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants \
  --source evals_inspectai/e2e/abbreviation_checker/data/example/baseline.md \
  --output-dir .local/example-variants

uv run flow run evals_inspectai/flow_config/abbreviation_checker_variants.py \
  --arg variants_dir=.local/example-variants --dry-run

uv run flow run evals_inspectai/flow_config/abbreviation_checker_structured_variants.py \
  --arg variants_dir=.local/example-variants --dry-run

uv run pytest tests/unit -n 4 -q --tb=short
uv run mypy .
git diff --check
```

The generator now requires explicit `--source` and `--output-dir`; references default
to the source's adjacent `references.json`. It edits annotated lines without reflow
and validates planned edits/reference maps before writing. Matching generated files
are replaced; unrelated variants are preserved, so use a fresh directory for a new
variant set. Both variant Flows accept `variants_dir`, `model`, and `epochs`.

Live backend/provider behavior and private-fork integration still need a maintainer
smoke test with approved credentials/data. The audit's verification is local and
mocked; it does not establish model quality or eliminate upstream HTTP 500 errors.

## Audit verification and PR follow-up

- Full unit suite: **1,486 passed, 3 skipped**. Existing deprecation/test warnings remain.
- `mypy .`: **446 source files, no errors**.
- Black check: all 50 changed/new Python files pass; `git diff --check` passes.
- Both variant Flows instantiate **22 synthetic-document tasks**, six samples each
  (two abbreviations × three epochs). The all-workflow smoke Flow instantiates 19 tasks.
  Dry-runs used a placeholder credential, no store, and locally redirected Flow state;
  no backend/model requests were made.
- All **32 private Markdown/reference files** are ignored; no DOCX remains in the
  active fixture tree. The only public fixture candidates are the README, synthetic
  Markdown, and its reference JSON. Candidate-file scans found no personal absolute
  paths, private gateway addresses, or common private-key/token signatures.
- `uv lock --check --offline`: passes (285 packages). The check needed execution
  outside the filesystem sandbox because uv's macOS configuration lookup panicked
  inside it; no packages were downloaded or installed.

The local `dev` branch is **25 commits behind the cached `origin/dev` reference**;
no fetch, merge, or rebase was performed. Update the eventual PR branch against its
chosen target and rerun checks. Cached upstream adds two more evals and changes the
dependency files, so review those when integrating rather than assuming this smoke
task list or lockfile can be copied unchanged. No new local commits existed at audit
time; these changes remain a proposed commit, not a published contribution.
