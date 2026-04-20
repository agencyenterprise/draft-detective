from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.solver import TaskState
from langchain_core.messages import BaseMessage
from langgraph.graph.state import RunnableConfig

from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.internal.common.config import get_model_or_agent_default
from evals_inspectai.internal.common.lc_agent_solver import langchain_agent
from lib.agents.reference_validator import (
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)


@task
def reference_validation():
    dataset = json_dataset(
        "../../e2e/reference_validation/dataset.json",
        FieldSpec(target="target_final_result", metadata=["target_answer"]),
    )

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(ReferenceValidatorAgent),
        solver=langchain_agent(
            ReferenceValidatorAgent,
            invoke_func=_invoke_reference_validator,
        ),
        scorer=[
            structured_output_scorer(
                model_type=BibliographyItemValidation, compare=_compare_final_result
            ),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


async def _invoke_reference_validator(
    agent: ReferenceValidatorAgent, input: str, config: RunnableConfig
) -> tuple[BibliographyItemValidation, list[BaseMessage]]:
    return await agent.ainvoke({"reference": input}, config=config)


def _compare_final_result(output: BibliographyItemValidation, state: TaskState) -> bool:
    return output.final_result.value == state.target.text
