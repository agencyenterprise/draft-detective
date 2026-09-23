"""Evaluate every abbreviation-checker Markdown variant over three independent epochs.

Runs one entries-task eval per Markdown file. Each eval contains the abbreviation samples
for only that document and uses the adjacent ``references.json``.

Usage:
    uv run flow run evals_inspectai/flow_config/abbreviation_checker_variants.py
"""

from pathlib import Path

from inspect_flow import FlowOptions, FlowSpec, FlowTask, models_matrix, tasks_matrix

_EVAL_DIR = Path(__file__).resolve().parent.parent / "e2e" / "abbreviation_checker"
_VARIANTS_DIR = _EVAL_DIR / "data" / "variants"
_TASK = f"{_EVAL_DIR}/abbreviation_checker_e2e.py@abbreviation_checker_entries"


def flow(
    backend: str = "remote",
    api_base_url: str | None = None,
    variants_dir: str | None = None,
    model: str = "openai/gpt-5.6-terra",
    epochs: int = 3,
) -> FlowSpec:
    """Use --arg backend=local to start repository code, or pass api_base_url."""
    directory = Path(variants_dir).resolve() if variants_dir else _VARIANTS_DIR
    documents = sorted(
        document
        for dataset in (directory / "single", directory / "multi")
        for document in dataset.glob("*.md")
        if document.is_file() and not document.name.startswith("~$")
    )
    if not documents:
        raise ValueError(
            f"No Markdown variants found under {directory}; supply the variant "
            "documents and their adjacent references.json files first."
        )
    return FlowSpec(
        log_dir="logs",
        options=FlowOptions(max_tasks=4),
        tasks=tasks_matrix(
            task=FlowTask(name=_TASK, epochs=epochs),
            args=[
                {
                    "data_dir": str(document.parent),
                    "reference_path": str(document.parent / "references.json"),
                    "filename": document.name,
                    "backend": backend,
                    "api_base_url": api_base_url,
                }
                for document in documents
            ],
            model=models_matrix(model=model),
        ),
    )
