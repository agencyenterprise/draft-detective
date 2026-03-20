# Evals (Inspect AI)

LLM evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/).

## Folder Structure

```
evals_inspectai/
├── common/                            # Shared utilities (scorers, comparers, API client, solver)
├── internal/                          # Evals that import agents directly from lib/
│   ├── abbreviation_checker/
│   ├── reference_text_extractor/
│   └── reference_validation/
└── e2e/                               # Evals that call the API end-to-end
    └── abbreviation_checker/
```

**Internal evals** invoke agents directly via Python imports. They require the full
codebase and its dependencies.

**E2E evals** trigger workflows through the HTTP API. They only depend on
`evals_inspectai/common/`, making them portable to a standalone repository in
the future.

## Available Evals

### Internal

| Eval | Description |
|------|-------------|
| `internal/abbreviation_checker` | Detects abbreviation compliance issues (missing inline definitions, abbreviations not in the Abbreviations section). |
| `internal/reference_text_extractor` | Extracts bibliographic reference entries from document reference/bibliography sections. |
| `internal/reference_validation` | Classifies bibliography items as `valid`, `not_found`, or `found_with_inconsistencies`. |

### E2E

| Eval | Description |
|------|-------------|
| `e2e/abbreviation_checker` | Same checks as the internal abbreviation checker, but runs the full workflow via the API. |

## Running Evals

All commands should be run from the project root.

### Internal evals

```bash
# Run a specific eval
uv run inspect eval evals_inspectai/internal/reference_validation/reference_validation.py

# Choose models
uv run inspect eval evals_inspectai/internal/abbreviation_checker/abbreviation_checker.py --model openai/gpt-4o

# Multiple epochs and sample limit
uv run inspect eval evals_inspectai/internal/reference_validation/reference_validation.py --epochs=2 --limit=5
```

### E2E evals

E2E evals require a running API server. Configure the following environment
variables before running:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EVAL_API_BASE_URL` | No | `http://localhost:8000` | Base URL of the API server |
| `EVAL_API_AUTH_TOKEN` | One of these | — | Pre-minted JWT Bearer token |
| `AUTH_SECRET` | One of these | — | Secret used to auto-generate a JWT |

```bash
# Start the API server first
uv run dev.py

# Run an e2e eval
uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py
```

## Viewing Results

Launch the Inspect AI log viewer to browse evaluation results interactively:

```bash
uv run inspect view
```

## Resources

- [Inspect AI Documentation](https://inspect.ai-safety-institute.org.uk/docs/)
