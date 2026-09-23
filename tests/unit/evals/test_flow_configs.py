from pathlib import Path

import pytest

from evals_inspectai.flow_config import (
    abbreviation_checker_multi,
    abbreviation_checker_variants,
    run_all_evals,
)


@pytest.mark.parametrize("backend", ["remote", "local"])
@pytest.mark.parametrize(
    "config", [abbreviation_checker_multi, abbreviation_checker_variants, run_all_evals]
)
def test_flow_forwards_backend_selection(monkeypatch, tmp_path, config, backend):
    # Do not depend on unpublished document fixtures.
    document = tmp_path / "single" / "variant.md"
    document.parent.mkdir()
    document.touch()
    monkeypatch.setattr(abbreviation_checker_variants, "_VARIANTS_DIR", tmp_path)
    endpoint = "https://deployment.example" if backend == "remote" else None
    spec = config.flow(backend=backend, api_base_url=endpoint)
    assert spec.tasks
    for task in spec.tasks:
        assert task.args["backend"] == backend
        assert task.args["api_base_url"] == endpoint
        task_file = Path(task.name.split("@")[0])
        assert task_file.is_absolute()
        assert task_file.is_file()
    if config is run_all_evals:
        assert spec.options.limit == 1
    if config is abbreviation_checker_variants:
        assert len(spec.tasks) == 1
        assert spec.tasks[0].args["filename"] == document.name


def test_variants_require_documents(monkeypatch, tmp_path):
    monkeypatch.setattr(abbreviation_checker_variants, "_VARIANTS_DIR", tmp_path)
    with pytest.raises(ValueError, match="No Markdown variants"):
        abbreviation_checker_variants.flow()
