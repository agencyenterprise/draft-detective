from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    exact,
    mean,
    model_graded_fact,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.config import (
    apply_inspectai_config_to_agent,
    get_model_or_agent_default,
    get_runnable_config,
)
from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.common.scorers import model_graded_check
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
            final_result_scorer(),
            model_graded_check(target_from_metadata="target_answer"),
        ],
    )


@scorer(metrics=[mean(), stderr()])
def final_result_scorer():
    async def score(state: TaskState, target: Target):
        target_final_result = target.text

        try:
            response = BibliographyItemValidation.model_validate_json(
                state.output.completion
            )
            if response.final_result.value == target_final_result:
                return Score(
                    value=CORRECT,
                    answer=response.final_result,
                    explanation="Final result matches target exactly",
                )
            else:
                return Score(
                    value=INCORRECT,
                    answer=response.final_result,
                    explanation=f"Expected '{target_final_result}', got '{response.final_result.value}'",
                )
        except ValidationError as e:
            return Score(
                value=INCORRECT,
                answer=state.output.completion,
                explanation=f"Error parsing response: {e}",
            )

    return score
