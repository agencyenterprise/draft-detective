"""No-network coverage of task discovery, native model calls, scoring and epochs."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from docx import Document
from inspect_ai import eval_async
from inspect_ai.model import ChatMessageUser, ModelName, ModelOutput, get_model
from inspect_ai.solver import TaskState
from langchain_core.messages import HumanMessage

from evals_inspectai.e2e.abbreviation_checker import (
    abbreviation_checker_structured as module,
)
from evals_inspectai.flow_config import (
    abbreviation_checker_structured_variants as flow_module,
)
from lib.agents.abbreviation_checker_structured import (
    ChunkExtraction,
    chunk_text,
    reconcile_chunks,
)
from lib.workflows.abbreviation_scan_v2.state import AbbreviationItem


def chunk_response():
    return ChunkExtraction(
        occurrences=[
            {
                "unit_id": 0,
                "surface": abbr,
                "match_number": number,
                "inline_definition": "",
                "ignored_reason": "",
            }
            for abbr, number in [("AI", 1), ("LLM", 1), ("AI", 2)]
        ],
        glossary=[],
        glossary_unit_ids=[],
        abbreviations_section_found=False,
    )


@pytest.fixture
def dataset(tmp_path):
    doc = Document()
    doc.add_paragraph("AI LLM AI")
    doc.save(tmp_path / "example.docx")
    entries = [
        AbbreviationItem(
            abbr=abbr,
            occurrence_number=number,
            inline_definition="",
            line_start=1,
            line_end=1,
        ).model_dump()
        for abbr, number in [("AI", 1), ("LLM", 1), ("AI", 2)]
    ]
    (tmp_path / "references.json").write_text(
        json.dumps(
            {
                "example.docx": {
                    "abbreviations": entries,
                    "abbreviations_section_found": False,
                },
            }
        )
    )
    return tmp_path


def test_task_has_one_sample_per_abbreviation_not_occurrence(dataset):
    task = module.abbreviation_checker_structured_entries(data_dir=str(dataset))
    assert [sample.id for sample in task.dataset] == [
        "example.docx::AI",
        "example.docx::LLM",
    ]
    assert len(json.loads(task.dataset[0].target)) == 2
    assert task.dataset[0].metadata["reference_file"] == str(
        dataset / "references.json"
    )


@pytest.mark.parametrize(
    "kind",
    [
        "reference_file",
        "document_reference",
        "filename",
        "coordinates",
        "empty_reference",
    ],
)
def test_bad_fixtures_fail_at_task_construction(dataset, kind):
    ref = dataset / "references.json"
    kwargs = {"data_dir": str(dataset)}
    if kind == "reference_file":
        kwargs["reference_path"] = str(dataset / "missing.json")
    elif kind == "document_reference":
        ref.write_text("{}")
    elif kind == "filename":
        kwargs["filename"] = "missing.docx"
    else:
        refs = json.loads(ref.read_text())
        if kind == "coordinates":
            refs["example.docx"]["source_format"] = "docx_body"
        else:
            refs["example.docx"]["abbreviations"] = []
        ref.write_text(json.dumps(refs))
    with pytest.raises(ValueError):
        module.abbreviation_checker_structured_entries(**kwargs)


@pytest.mark.asyncio
async def test_adapter_uses_inspect_native_schema_no_tools_or_cache(monkeypatch):
    generate = AsyncMock(
        return_value=ModelOutput.from_content(
            model="mockllm/model",
            content=chunk_response().model_dump_json(),
        )
    )
    monkeypatch.setattr(module, "get_model", lambda: SimpleNamespace(generate=generate))
    runnable = module.InspectStructuredModel().with_structured_output(
        ChunkExtraction,
        method="json_schema",
        strict=True,
        include_raw=True,
    )
    result = await runnable.ainvoke([HumanMessage(content="source, not references")])
    assert result["parsed"] == chunk_response()
    kwargs = generate.call_args.kwargs
    assert kwargs["tools"] == []
    assert kwargs["cache"] is False
    assert kwargs["config"].max_retries == 0
    schema = kwargs["config"].response_schema
    assert schema.strict
    # Pydantic $refs must be resolved, not lost while converting the nested schema.
    item_schema = schema.json_schema.properties["occurrences"].items
    assert item_schema.properties["unit_id"].type == "integer"
    assert item_schema.additionalProperties is False


@pytest.mark.parametrize("reason", ["max_tokens", "content_filter"])
@pytest.mark.asyncio
async def test_adapter_rejects_incomplete_responses(monkeypatch, reason):
    output = ModelOutput.from_content(
        model="mockllm/model", content=chunk_response().model_dump_json()
    )
    output.choices[0].stop_reason = reason
    monkeypatch.setattr(
        module,
        "get_model",
        lambda: SimpleNamespace(generate=AsyncMock(return_value=output)),
    )
    runnable = module.InspectStructuredModel().with_structured_output(
        ChunkExtraction,
        method="json_schema",
        strict=True,
        include_raw=True,
    )
    with pytest.raises(ValueError, match="did not complete"):
        await runnable.ainvoke([HumanMessage(content="source")])


def _state(path, abbr="AI", epoch=1):
    return TaskState(
        model=ModelName("mockllm/model"),
        sample_id=f"example.docx::{abbr}",
        epoch=epoch,
        input=str(path),
        messages=[ChatMessageUser(content=str(path))],
    )


@pytest.mark.asyncio
async def test_failed_extraction_not_reused(monkeypatch, dataset):
    result = reconcile_chunks("AI LLM AI", chunk_text("AI LLM AI"), [chunk_response()])
    check = AsyncMock(side_effect=[RuntimeError("chunk failed"), result])
    monkeypatch.setattr(
        module, "sample_active", lambda: SimpleNamespace(eval_id="test")
    )
    monkeypatch.setattr(
        module,
        "StructuredAbbreviationChecker",
        lambda *a, **k: SimpleNamespace(check_file=check),
    )
    solve = module.structured_abbreviation_solver()
    with pytest.raises(RuntimeError, match="chunk failed"):
        await solve(_state(dataset / "example.docx"), None)
    state = await solve(_state(dataset / "example.docx"), None)
    assert len(json.loads(state.output.completion)["abbreviations"]) == 3
    assert check.await_count == 2


@pytest.mark.asyncio
async def test_timeout_is_not_cached(monkeypatch, dataset):
    async def slow(path):
        await asyncio.sleep(1)

    check = AsyncMock(side_effect=slow)
    monkeypatch.setattr(
        module, "sample_active", lambda: SimpleNamespace(eval_id="test")
    )
    monkeypatch.setattr(
        module,
        "StructuredAbbreviationChecker",
        lambda *a, **k: SimpleNamespace(check_file=check),
    )
    solve = module.structured_abbreviation_solver(timeout_s=0.001)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            await solve(_state(dataset / "example.docx"), None)
    assert check.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("source_format", ["md", "docx"])
async def test_real_inspect_run_scores_all_rows_and_extracts_fresh_each_epoch_and_run(
    dataset, tmp_path, monkeypatch, source_format
):
    # Uses the real Inspect scheduler, scorer, model logger and Markdown converter.
    # Only model inference is replaced; no API requests or private fixtures.
    monkeypatch.setenv("INSPECT_DISPLAY", "none")
    if source_format == "md":
        (dataset / "example.md").write_text("AI LLM AI", encoding="utf-8")
        reference_path = dataset / "references.json"
        refs = json.loads(reference_path.read_text())
        refs["example.md"] = refs["example.docx"]
        reference_path.write_text(json.dumps(refs))
        monkeypatch.setattr(
            "lib.agents.abbreviation_checker_structured.convert_to_markdown",
            AsyncMock(side_effect=AssertionError("Markdown must bypass conversion")),
        )
    from inspect_ai._util import appdirs

    monkeypatch.setattr(
        appdirs, "user_data_path", lambda *a, **k: tmp_path / "inspect-data"
    )
    monkeypatch.setattr(
        appdirs, "user_cache_path", lambda *a, **k: tmp_path / "inspect-cache"
    )
    requests = []

    def respond(input, tools, tool_choice, config):
        requests.append((input, config))
        assert tools == []
        assert config.response_schema.name == "ChunkExtraction"
        assert json.loads(input[-1].text)[0]["text"] == "AI LLM AI"
        return ModelOutput.from_content(
            model="mockllm/model", content=chunk_response().model_dump_json()
        )

    model = get_model("mockllm/model", custom_outputs=respond, memoize=False)
    task = module.abbreviation_checker_structured_entries(data_dir=str(dataset))
    for epochs in (3, 1):
        logs = await eval_async(
            task,
            model=model,
            epochs=epochs,
            max_samples=6,
            log_dir=str(tmp_path / f"logs-{epochs}"),
            log_format="json",
            fail_on_error=True,
            retry_on_error=0,
            ctl_server=False,
        )
        assert logs[0].status == "success", logs[0].error
        assert len(logs[0].samples) == 2 * epochs
        assert (
            sum(
                len([event for event in sample.events if event.event == "model"])
                for sample in logs[0].samples
            )
            == epochs
        )
        for sample in logs[0].samples:
            score = sample.scores["single_entry_scorer"]
            assert score.value == 1.0
            assert set(score.metadata) == {
                "TOTAL",
                "TP",
                "FP",
                "TN",
                "FN",
                "characterization",
            }
            assert score.metadata["FP"] == score.metadata["FN"] == 0
            assert sample.metadata["structured_extraction"]["epoch"] == sample.epoch
            assert sample.metadata["structured_extraction"]["chunk_count"] == 1
            assert sample.metadata["structured_extraction"]["converter"] == (
                "none" if source_format == "md" else "markitdown"
            )
    # Not six extractions for six rows, not one cached extraction across epochs,
    # and not a stale result when the same Task object is evaluated again.
    assert len(requests) == 4


def test_variant_flow_one_task_per_document(monkeypatch, tmp_path):
    single = tmp_path / "single"
    single.mkdir()
    for name in ("one.md", "two.md", "one.docx"):
        (single / name).touch()
    monkeypatch.setattr(flow_module, "_VARIANTS_DIR", tmp_path)
    spec = flow_module.flow(model="mockllm/model", chunk_chars=4096)
    assert len(spec.tasks) == 2
    assert {task.args["filename"] for task in spec.tasks} == {"one.md", "two.md"}
    assert all(task.args["chunk_chars"] == 4096 for task in spec.tasks)
    assert all(task.epochs == 3 for task in spec.tasks)
    assert all("backend" not in task.args for task in spec.tasks)


def test_variant_flow_requires_documents(monkeypatch, tmp_path):
    monkeypatch.setattr(flow_module, "_VARIANTS_DIR", tmp_path)
    with pytest.raises(ValueError, match="No Markdown variants"):
        flow_module.flow()
