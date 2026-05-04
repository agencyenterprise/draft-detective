from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.solver import TaskState
from langchain_core.messages import BaseMessage
from langgraph.graph.state import RunnableConfig

from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.internal.common.config import get_model_or_agent_default
from evals_inspectai.internal.common.lc_agent_solver import langchain_agent
from lib.agents.reference_validator_v2 import (
    BibliographyItemValidationV2,
    ReferenceValidatorV2Agent,
)


@task
def reference_validation():
    dataset = json_dataset(
        "../../e2e/reference_validation/dataset.json",
        FieldSpec(target="target_final_result", metadata=["target_answer"]),
    )

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(ReferenceValidatorV2Agent),
        solver=langchain_agent(
            ReferenceValidatorV2Agent,
            invoke_func=_invoke_reference_validator,
        ),
        scorer=[
            structured_output_scorer(
                model_type=BibliographyItemValidationV2,
                compare=_compare_final_result,
            ),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


async def _invoke_reference_validator(
    agent: ReferenceValidatorV2Agent, input: str, config: RunnableConfig
) -> tuple[BibliographyItemValidationV2, list[BaseMessage]]:
    return await agent.ainvoke({"reference": input}, config=config)


def _compare_final_result(
    output: BibliographyItemValidationV2, state: TaskState
) -> bool:
    return output.final_result.value == state.target.text
