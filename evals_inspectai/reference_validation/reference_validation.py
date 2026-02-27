from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.solver import TaskState

from evals_inspectai.common.config import (
    apply_inspectai_config_to_agent,
    get_model_or_agent_default,
    get_runnable_config,
)
from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from lib.agents.reference_validator import (
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)
from tests.conftest import create_test_context


@agent
def reference_validation_agent() -> Agent:
    context = create_test_context()

    async def execute(state: AgentState) -> AgentState:
        ref_agent = ReferenceValidatorAgent(context)
        apply_inspectai_config_to_agent(ref_agent)

        user_input = state.messages[0].text if state.messages else ""
        response, lc_messages = await ref_agent.ainvoke(
            {"reference": user_input}, config=get_runnable_config()
        )

        state.output = ModelOutput(
            completion=response.model_dump_json(),
            model=ref_agent.model.get_model_name_for_inspectai(),
        )
        state.messages = messages_from_langchain(lc_messages)

        return state

    return execute


@task
def reference_validation():
    dataset = json_dataset(
        "dataset.jsonl",
        FieldSpec(target="target_final_result", metadata=["target_answer"]),
    )

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(ReferenceValidatorAgent),
        solver=reference_validation_agent(),
        scorer=[
            structured_output_scorer(
                model_type=BibliographyItemValidation, compare=_compare_final_result
            ),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


def _compare_final_result(output: BibliographyItemValidation, state: TaskState) -> bool:
    return output.final_result.value == state.target.text
