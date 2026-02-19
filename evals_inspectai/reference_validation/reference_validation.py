from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState, generate, system_message, use_tools
from inspect_ai.tool import web_search
from pydantic import ValidationError

from evals_inspectai.common import generate_config_for_agent, get_model_or_agent_default
from lib.agents.reference_validator import (
    SYSTEM_PROMPT,
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)


@task
def reference_validation():
    dataset = json_dataset("dataset.jsonl")

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(ReferenceValidatorAgent),
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(web_search("openai")),
            generate(),
        ],
        scorer=final_result_scorer(),
        config=generate_config_for_agent(
            ReferenceValidatorAgent, BibliographyItemValidation
        ),
    )


@scorer(metrics=[mean(), stderr()])
def final_result_scorer():
    async def score(state: TaskState, target: Target):
        try:
            response = BibliographyItemValidation.model_validate_json(
                state.output.completion
            )
            if response.final_result.value == target.text:
                return Score(
                    value=CORRECT,
                    answer=response.final_result,
                    explanation="Final result matches target exactly",
                )
            else:
                return Score(
                    value=INCORRECT,
                    answer=response.final_result,
                    explanation=f"Expected '{target.text}', got '{response.final_result.value}'",
                )
        except ValidationError as e:
            return Score(
                value=INCORRECT,
                answer=state.output.completion,
                explanation=f"Error parsing response: {e}",
            )

    return score
