"""Evaluate the non-agent checker against the existing Markdown-based references.

    inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_structured.py@abbreviation_checker_structured_entries \
        --model openai/gpt-5.6-terra --epochs 3

One sample per reference abbreviation. Markdown fixtures are read directly;
legacy DOCX inputs use MarkItDown. Each document is extracted once per epoch.
Sibling abbreviation samples share that completed result, not model responses
across epochs. Model calls go through Inspect (native response schema, no tools),
so --model / -G settings, transcripts, token usage and connection limits apply.
The first sample doing the extraction owns its model-call events and usage;
siblings record its sample ID. No backend API, database or agent loop is used.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset
from inspect_ai.log._samples import sample_active
from inspect_ai.model import GenerateConfig, ModelOutput, ResponseSchema, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import json_schema
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.e2e.abbreviation_checker.fixtures import (
    document_files,
    entry_samples,
)
from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import (
    single_entry_scorer,
)
from lib.agents.abbreviation_checker_structured import (
    StructuredAbbreviationChecker,
    StructuredAbbreviationResult,
    chunk_text,
)

_EVAL_DIR = Path(__file__).resolve().parent
_ROOT = _EVAL_DIR.parents[2]


class InspectStructuredModel:
    """Use Inspect's selected model without routing calls outside the eval logger."""

    def with_structured_output(
        self, schema: type[BaseModel], **kwargs: Any
    ) -> Runnable:
        if kwargs != {"method": "json_schema", "strict": True, "include_raw": True}:
            raise ValueError("Only native strict JSON-schema output is supported")
        response_schema = ResponseSchema(
            name=schema.__name__, json_schema=json_schema(schema), strict=True
        )

        async def invoke(messages: list[BaseMessage]) -> dict[str, Any]:
            output = await get_model().generate(
                input=messages_from_langchain(messages),
                tools=[],
                config=GenerateConfig(response_schema=response_schema, max_retries=0),
                cache=False,
            )
            if not output.choices:
                raise ValueError("Structured chunk returned no model choices")
            if output.message.tool_calls:
                raise ValueError("Structured chunks must not return tool calls")
            if output.choices[0].stop_reason != "stop":
                raise ValueError(
                    f"Structured chunk did not complete: {output.choices[0].stop_reason}"
                )
            return {
                "parsed": schema.model_validate_json(output.completion),
                "raw": AIMessage(content=output.completion),
                "parsing_error": None,
            }

        return RunnableLambda(invoke)


@dataclass
class _DocumentResult:
    result: StructuredAbbreviationResult
    sample_id: str | int


@solver
def structured_abbreviation_solver(
    chunk_chars: int = 8000,
    context_chars: int = 1500,
    max_concurrency: int = 4,
    timeout_s: float = 1800,
) -> Solver:
    """Share only successful document results within one evaluation/model/epoch.

    This sharing is fan-out to scoring rows, not reuse between trials. A failure
    never populates results, allowing Inspect retry to perform a fresh extraction.
    Native model retries/cache are disabled; Inspect sample retry remains available.
    """
    if timeout_s <= 0 or max_concurrency < 1:
        raise ValueError("timeout_s and max_concurrency must be positive")
    chunk_text("", chunk_chars=chunk_chars, context_chars=context_chars)
    results: dict[tuple[str, str, str, int], _DocumentResult] = {}
    locks: dict[tuple[str, str, str, int], asyncio.Lock] = {}

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        active = sample_active()
        if active is None:
            raise RuntimeError(
                "Structured evaluation requires an active Inspect sample"
            )
        path = Path(state.input_text).resolve()
        key = (active.eval_id, str(state.model), str(path), state.epoch)
        lock = locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in results:
                checker = StructuredAbbreviationChecker(
                    InspectStructuredModel(),
                    chunk_chars=chunk_chars,
                    context_chars=context_chars,
                    max_concurrency=max_concurrency,
                )
                async with asyncio.timeout(timeout_s):
                    result = await checker.check_file(path)
                results[key] = _DocumentResult(result, state.sample_id)
        shared = results[key]
        result = shared.result
        # Convert anew for each sample: state.messages is mutable.
        state.messages = messages_from_langchain(result.messages)
        state.output = ModelOutput(
            model=str(state.model),
            completion=json.dumps(
                {
                    "abbreviations": [
                        item.model_dump() for item in result.abbreviations
                    ],
                    **result.output.model_dump(),
                    "source_text": result.source_text,
                }
            ),
        )
        state.metadata["structured_extraction"] = {
            "epoch": state.epoch,
            "source_sample_id": shared.sample_id,
            "shared_within_epoch": shared.sample_id != state.sample_id,
            "chunk_count": result.chunk_count,
            "converter": (
                "none" if path.suffix.lower() in {".md", ".markdown"} else "markitdown"
            ),
            "warnings": list(result.warnings),
        }
        return state

    return solve


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _ROOT / p


@task
def abbreviation_checker_structured_entries(
    data_dir: str | None = None,
    reference_path: str | None = None,
    filename: str | None = None,
    chunk_chars: int = 8000,
    context_chars: int = 1500,
    max_concurrency: int = 4,
    timeout_s: float = 1800,
) -> Task:
    """Same abbreviation rows/scorer as the agent eval, but using structured chunks.

    data_dir defaults to adjacent data/. References default to references.json in
    that directory. filename restricts the task to one document (for per-document Flow
    logs). References are required; missing fixtures fail before any model calls.
    max_concurrency bounds chunk calls per document extraction; --max-connections
    bounds requests across concurrent documents/epochs. Use --epochs for repeats.
    """
    directory = _resolve(data_dir) if data_dir else _EVAL_DIR / "data"
    references = (
        _resolve(reference_path) if reference_path else directory / "references.json"
    )
    documents = [
        p
        for p in document_files(directory, filename)
        if p.suffix.lower() in {".md", ".markdown", ".docx"}
    ]
    if not documents:
        raise ValueError(
            f"No matching Markdown or DOCX files in {directory} (filename={filename!r})"
        )
    samples = entry_samples(documents, references)
    return Task(
        dataset=MemoryDataset(samples),
        fail_on_error=0.2,
        solver=structured_abbreviation_solver(
            chunk_chars=chunk_chars,
            context_chars=context_chars,
            max_concurrency=max_concurrency,
            timeout_s=timeout_s,
        ),
        scorer=single_entry_scorer(),
    )
