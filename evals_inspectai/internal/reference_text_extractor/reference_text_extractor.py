from inspect_ai import task, task_with
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.scorers import structured_output_scorer
from evals_inspectai.e2e.reference_text_extractor.reference_text_extractor_e2e import (
    reference_text_extractor_e2e,
)
from evals_inspectai.internal.common.config import get_model_or_agent_default
from evals_inspectai.internal.common.lc_agent_solver import langchain_agent
from lib.agents.reference_text_extractor_v2 import (
    ReferenceExtractorV2Agent,
    ReferenceExtractorV2Output,
)


@task
def reference_text_extractor():
    base_task = reference_text_extractor_e2e()
    return task_with(
        base_task,
        model=get_model_or_agent_default(ReferenceExtractorV2Agent),
        solver=langchain_agent(ReferenceExtractorV2Agent),
        scorer=[
            structured_output_scorer(ReferenceExtractorV2Output, _compare_references),
        ],
    )


def _compare_references(output: ReferenceExtractorV2Output, state: TaskState) -> Score:
    expected_refs: list[str] = state.metadata.get("target_references", [])
    actual_refs = [ref.text for ref in output.references]
    return deep_diff_score(expected_refs, actual_refs)
