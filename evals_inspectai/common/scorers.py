import re
from typing import Callable, TypeVar

from inspect_ai.model import Model, get_model
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
    scorer,
    stderr,
)
from inspect_ai.scorer._model import (  # type: ignore[attr-defined]
    DEFAULT_GRADE_PATTERN,
    DEFAULT_MODEL_GRADED_FACT_TEMPLATE,
    default_instructions,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import resource
from pydantic import BaseModel, ValidationError

DEFAULT_GRADER_MODEL = "openai/gpt-5.4"


@scorer(metrics=[accuracy(), stderr()])
def model_graded_check(
    target_from_metadata: str | None = None,
    template: str = DEFAULT_MODEL_GRADED_FACT_TEMPLATE,
    grade_pattern: str = DEFAULT_GRADE_PATTERN,
    instructions: str | None = None,
    model: str | Model | None = None,
    partial_credit: bool = False,
) -> Scorer:
    """Model-graded scorer that uses an LLM to evaluate answer correctness.

    Formats a grading prompt from the given template with the task's question,
    model answer, and target criterion, then asks a grader model to score it.
    Supports reading the target criterion from sample metadata instead of the
    default target, which is useful when the grading rubric is stored alongside
    the dataset rather than in a static target string.

    Args:
        target_from_metadata: If set, reads the target criterion from
            ``state.metadata[target_from_metadata]`` instead of ``target.text``.
        template: Grading prompt template with ``{question}``, ``{answer}``,
            ``{criterion}``, and ``{instructions}`` placeholders.
        grade_pattern: Regex used to extract the grade from the grader's output.
        instructions: Custom grading instructions. Defaults to the built-in
            instructions (with optional partial-credit wording).
        model: Model used for grading. Defaults to the currently active model.
        partial_credit: When ``True``, default instructions allow partial credit.

    Returns:
        A ``Scorer`` coroutine that yields a ``Score`` with the extracted grade.
    """
    # resolve grading template and instructions,
    # (as they could be file paths or URLs)
    template = resource(template)
    instructions = (
        resource(instructions)
        if instructions
        else default_instructions(partial_credit=partial_credit)
    )

    async def score(state: TaskState, target: Target) -> Score:
        if target_from_metadata:
            target_text = state.metadata[target_from_metadata]
        else:
            target_text = target.text

        # resolve model
        grader_model = get_model(model) if model else get_model(DEFAULT_GRADER_MODEL)
        assert grader_model is not None, "No model provided and no active model found"

        # format the model grading template
        score_prompt = template.format(
            question=state.input_text,
            answer=state.output.completion,
            criterion=target_text,
            instructions=instructions,
        )

        # query the model for the score
        result = await grader_model.generate(score_prompt)

        # extract the grade
        match = re.search(grade_pattern, result.completion)
        if match:
            return Score(
                value=match.group(1),
                answer=match.group(0),
                explanation=result.completion,
            )
        else:
            return Score(
                value=INCORRECT,
                explanation="Grade not found in model output: "
                + f"{result.completion}",
            )

    return score


ModelType = TypeVar("ModelType", bound=BaseModel)


@scorer(metrics=[mean(), stderr()])
def structured_output_scorer(
    model_type: type[ModelType],
    compare: Callable[[ModelType, TaskState], bool | Score],
) -> Scorer:
    """Scorer that parses the agent output as a Pydantic model and compares against the target.

    Parses ``state.output.completion`` using ``model_type.model_validate_json``,
    then delegates the scoring to ``compare``, which receives the parsed model
    instance and the full task state.

    Args:
        model_type: Pydantic model class used to parse the agent's JSON output.
        compare: Callable that receives the parsed model instance and the
            task state. Can return a ``bool`` (``True`` → CORRECT, ``False`` →
            INCORRECT) or a ``Score`` object directly for custom values/explanations.

    Returns:
        A ``Scorer`` coroutine that yields the resulting ``Score``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        try:
            structured_output = model_type.model_validate_json(state.output.completion)
        except ValidationError as e:
            return Score(
                value=INCORRECT,
                answer=state.output.completion,
                explanation=f"Error parsing response: {e}",
            )

        result = compare(structured_output, state)
        if isinstance(result, Score):
            return result
        if result:
            return Score(value=CORRECT, explanation="Field value matches target")
        return Score(
            value=INCORRECT,
            explanation=f"Field value does not match target '{target.text}'",
        )

    return score
