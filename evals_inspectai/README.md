# Evals (Inspect AI)

LLM evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/).

## Available Evals

### Reference Validation

Evaluates the reference validator agent's ability to classify bibliography items as `valid`, `not_found`, or `found_with_inconsistencies`.

- **Task file:** `evals_inspectai/reference_validation/reference_validation.py`
- **Dataset:** `evals_inspectai/reference_validation/dataset.jsonl`

### Abbreviation Checker

Evaluates the abbreviation checker agent's ability to detect abbreviation compliance issues: missing inline definitions at first use and abbreviations not listed in the dedicated Abbreviations section.

- **Task file:** `evals_inspectai/abbreviation_checker/abbreviation_checker.py`
- **Dataset:** `evals_inspectai/abbreviation_checker/dataset.json`

## Running Evals

All commands should be run from the project root.

```bash
# Run a specific eval with specific models
uv run inspect eval evals_inspectai/reference_validation/reference_validation.py --model openai/gpt-5.2,openai/gpt-4o

# Run with multiple epochs (repeated runs per sample)
uv run inspect eval evals_inspectai/reference_validation/reference_validation.py --epochs=2

# Limit to a subset of samples
uv run inspect eval evals_inspectai/reference_validation/reference_validation.py --limit=5

# Combine options
uv run inspect eval evals_inspectai/reference_validation/reference_validation.py --model openai/gpt-4o --epochs=3 --limit=10
```

## Viewing Results

Launch the Inspect AI log viewer to browse evaluation results interactively:

```bash
uv run inspect view
```

## Resources

- [Inspect AI Documentation](https://inspect.ai-safety-institute.org.uk/docs/)

