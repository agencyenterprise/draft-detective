from pathlib import Path
from typing import List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer

CHECK_TYPES = ("trigger_words", "advocacy_language", "subjective_tone")


class LLMVerification(BaseModel):
    confirmed: bool
    explanation: str = ""
    word_positions: List[int] = Field(default_factory=list)


class ProceduralFlags(BaseModel):
    trigger_words: bool = False
    advocacy_language: bool = False
    subjective_tone: bool = False


class ChunkResult(BaseModel):
    chunk_index: int
    procedural_flags: ProceduralFlags = Field(default_factory=ProceduralFlags)
    llm_trigger_words: Optional[LLMVerification] = None
    llm_advocacy_language: Optional[LLMVerification] = None
    llm_subjective_tone: Optional[LLMVerification] = None


class AdvocacyToneOutput(BaseModel):
    results: List[ChunkResult] = Field(default_factory=list)


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=record["input"],
        target=record.get("target_answer", ""),
        metadata={"expected_confirmed": record.get("expected_confirmed", {})},
    )


@task
def advocacy_tone_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent("advocacy_tone", timeout_s=600),
        scorer=[
            structured_output_scorer(AdvocacyToneOutput, _compare_llm_decisions),
            model_graded_check(partial_credit=True),
        ],
    )


def _collect_confirmed(output: AdvocacyToneOutput) -> dict[str, list[bool]]:
    """Return all confirmed values per check type, across every chunk."""
    runs: dict[str, list[bool]] = {ct: [] for ct in CHECK_TYPES}
    for chunk in output.results:
        for ct in CHECK_TYPES:
            verification = getattr(chunk, f"llm_{ct}")
            if verification is not None:
                runs[ct].append(verification.confirmed)
    return runs


def _compare_llm_decisions(output: AdvocacyToneOutput, state: TaskState) -> Score:
    expected: dict = state.metadata.get("expected_confirmed", {})
    actual = _collect_confirmed(output)

    mismatches: list[str] = []
    for ct in CHECK_TYPES:
        exp = expected.get(ct)
        runs = actual[ct]
        if exp is None:
            if runs:
                mismatches.append(
                    f"{ct}: expected no LLM verification, got {runs}"
                )
        else:
            if exp not in runs:
                mismatches.append(
                    f"{ct}: expected confirmed={exp}, got runs={runs}"
                )

    if mismatches:
        return Score(value=0.0, explanation="; ".join(mismatches))
    return Score(value=1.0, explanation="All LLM verifications match expected")
