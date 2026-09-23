"""One structured-checker task per Markdown variant, three independent epochs each.

    flow run evals_inspectai/flow_config/abbreviation_checker_structured_variants.py --dry-run

No backend selection: extraction runs directly in the Inspect process.
"""

from pathlib import Path

from inspect_flow import FlowOptions, FlowSpec, FlowTask, models_matrix, tasks_matrix

_EVAL_DIR = Path(__file__).resolve().parent.parent / "e2e" / "abbreviation_checker"
_VARIANTS_DIR = _EVAL_DIR / "data" / "variants"
_TASK = f"{_EVAL_DIR}/abbreviation_checker_structured.py@abbreviation_checker_structured_entries"


def flow(
    model: str = "openai/gpt-5.6-terra",
    chunk_chars: int = 8000,
    context_chars: int = 1500,
    max_concurrency: int = 4,
    variants_dir: str | None = None,
    epochs: int = 3,
) -> FlowSpec:
    directory = Path(variants_dir).resolve() if variants_dir else _VARIANTS_DIR
    documents = sorted(
        document
        for dataset in (directory / "single", directory / "multi")
        for document in dataset.glob("*.md")
        if document.is_file() and not document.name.startswith("~$")
    )
    if not documents:
        raise ValueError(f"No Markdown variants found under {directory}")
    return FlowSpec(
        log_dir="logs-structured",
        options=FlowOptions(max_tasks=4),
        tasks=tasks_matrix(
            task=FlowTask(name=_TASK, epochs=epochs),
            args=[
                {
                    "data_dir": str(document.parent),
                    "reference_path": str(document.parent / "references.json"),
                    "filename": document.name,
                    "chunk_chars": chunk_chars,
                    "context_chars": context_chars,
                    "max_concurrency": max_concurrency,
                }
                for document in documents
            ],
            model=models_matrix(model=model),
        ),
    )
