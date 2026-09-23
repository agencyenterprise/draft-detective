# Full-document abbreviation fixtures

`example/` is a small, synthetic public fixture. It includes repeated abbreviations,
a Markdown table, and an abbreviation glossary. It contains no source-document material.

All other files here are local-only and ignored by Git, including source documents,
Markdown snapshots, generated variants, and reference JSON. Markdown conversion does
not make a private document safe to publish. Keep private fixtures in the private fork
or an approved dataset store; do not force-add them to the public PR.

Reference keys are document filenames. Occurrence line numbers are one-based lines in
the exact Markdown file; do not reflow text without updating the references. Glossary
entries are definitions, not body occurrences.

Run the public fixture by passing
`-T data_dir=evals_inspectai/e2e/abbreviation_checker/data/example` to either entries task.
Variant Flow configs accept `--arg variants_dir=...`, pointing at a directory containing
`single/` and `multi/`, each with Markdown documents and an adjacent `references.json`.

To generate disposable public examples without touching local research fixtures:

```bash
uv run python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants \
  --source evals_inspectai/e2e/abbreviation_checker/data/example/baseline.md \
  --output-dir .local/example-variants
```
