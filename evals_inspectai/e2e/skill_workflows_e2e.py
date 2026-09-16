"""E2E eval tasks for every skill-declared workflow that has a dataset.

There is no per-workflow task module for skill-declared checks. This module
reads the workflow blocks from ``skills/*/SKILL.md`` and, for each declared
slug with an ``evals_inspectai/e2e/<slug>/dataset.yaml``, registers a task
named ``<slug>_e2e``. Adding an eval is adding that dataset file.

Run one::

    uv run inspect eval evals_inspectai/e2e/skill_workflows_e2e.py@active_voice_e2e

Run all skill-declared workflows that have datasets::

    uv run inspect eval evals_inspectai/e2e/skill_workflows_e2e.py

The backend must be running (``uv run dev.py``).
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.skill_workflow_task import skill_workflow_task
from lib.skill_workflow_spec import read_all_skill_workflow_declarations

_E2E_DIR = Path(__file__).parent


def _make_task(slug: str, dataset_path: Path):
    def _task() -> Task:
        return skill_workflow_task(slug, dataset_path)

    _task.__name__ = f"{slug}_e2e"
    _task.__qualname__ = _task.__name__
    return task(name=_task.__name__)(_task)


def _register_all() -> dict[str, object]:
    registered: dict[str, object] = {}
    for declaration in read_all_skill_workflow_declarations():
        dataset_path = _E2E_DIR / declaration.type_slug / "dataset.yaml"
        if dataset_path.is_file():
            registered[f"{declaration.type_slug}_e2e"] = _make_task(
                declaration.type_slug, dataset_path
            )
    return registered


# Expose each task as a module attribute so `file.py@task_name` resolves.
globals().update(_register_all())
