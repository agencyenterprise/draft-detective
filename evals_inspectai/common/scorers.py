import asyncio
import re
import statistics
from typing import Any, Callable, Mapping, Sequence, TypeVar

from inspect_ai.model import ChatMessageAssistant, Model, get_model
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
    metric,
    scorer,
    stderr,
    value_to_float,
)
from inspect_ai.scorer._model import (  # type: ignore[attr-defined]
    DEFAULT_GRADE_PATTERN,
    DEFAULT_MODEL_GRADED_FACT_TEMPLATE,
    default_instructions,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import resource
from pydantic import BaseModel, ValidationError

from evals_inspectai.common.loaders import references_local_images

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
    The answer is the workflow's full output (``state.output.completion``, the
    serialised workflow state for the e2e evals), graded against the sample's
    target answer as C / I, or C / P / I with ``partial_credit``.
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
        model: Model used for grading. Defaults to ``DEFAULT_GRADER_MODEL``.
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


# --- Per-check and per-criterion scoring -----------------------------------
#
# The helpers below back the "one metric per check" pattern: a scorer returns a
# dict-valued Score and declares `metrics={name: [mean(), stderr()]}`, so every
# check names itself in the results table instead of being averaged into a
# single number a reader has to decode from an explanation string. Inspect
# raises when a declared metric key is missing from any sample's score, so every
# code path has to return the full key set -- which is what `failed_score` is
# for.


def failed_score(keys: Sequence[str], reason: str) -> Score:
    """Score every key as failed, for an output there is nothing to check in."""
    return Score(value={key: 0.0 for key in keys}, explanation=reason)


def checks_to_score(checks: Mapping[str, tuple[bool | float, str]]) -> Score:
    """Turn per-check results into a dict-valued Score.

    A check is usually a bool, but may be a fraction when the check is over a
    set of items (say, how many of the expected findings were located). Whole
    values read as PASS / FAIL and anything between shows the number, so the
    explanation stays scannable either way.
    """

    def label(ok: bool | float) -> str:
        value = float(ok)
        if value == 1.0:
            return "PASS"
        if value == 0.0:
            return "FAIL"
        return f"{value:.2f}"

    return Score(
        value={name: float(ok) for name, (ok, _) in checks.items()},
        explanation=" | ".join(
            f"{label(ok)} {name}: {detail}" for name, (ok, detail) in checks.items()
        ),
    )


# --- Judged criteria -------------------------------------------------------

# C / P / I as the grader returns them.
GRADE_VALUES = {"C": 1.0, "P": 0.5, "I": 0.0}

# Inspect's fact template asks "does the submission contain the content in the
# expert answer?", which suits a criterion describing what the output should
# say. It misgrades a criterion that states a *property* the output must have --
# the grader looks for the submission to restate the rule and marks a compliant
# output partial for not discussing it. This template asks for verification
# instead, and is the one to pass for requirement-shaped criteria.
REQUIREMENT_TEMPLATE = """
You are checking whether a submitted document review satisfies one specific requirement.

[BEGIN DATA]
************
[Document under review]: {question}
************
[Requirement]: {criterion}
************
[Submission]: {answer}
************
[END DATA]

Decide whether the submission satisfies the requirement. Judge the submission's own
content and decisions against the requirement. The submission is not expected to
restate, quote or discuss the requirement itself, and must not be penalised for
not doing so. Ignore differences of style, grammar and punctuation.

{instructions}
"""


def criteria_for(state: TaskState, shared: dict[str, str]) -> dict[str, str]:
    """Shared criteria, with any per-sample text from the dataset layered on."""
    overrides = (state.metadata or {}).get("rubric") or {}
    return {**shared, **overrides}


async def _grade_one(
    grader: Model, criterion: str, answer: str, question: str, template: str
) -> tuple[float, str]:
    """Grade a single criterion, returning its value and the grader's reasoning."""
    prompt = template.format(
        question=question,
        answer=answer,
        criterion=criterion,
        instructions=default_instructions(partial_credit=True),
    )
    result = await grader.generate(prompt)
    match = re.search(DEFAULT_GRADE_PATTERN, result.completion)
    if not match:
        return 0.0, f"grade not found in grader output: {result.completion[:300]}"
    return GRADE_VALUES.get(match.group(1), 0.0), result.completion


async def grade_criteria(
    grader: Model,
    keys: Sequence[str],
    criteria: dict[str, str],
    answer: str,
    question: str,
    template: str = DEFAULT_MODEL_GRADED_FACT_TEMPLATE,
    calls_per_criterion: int = 1,
) -> Score:
    """Grade each criterion in its own call, concurrently, into one Score.

    One grader call per criterion rather than one call weighing all of them.
    Judging them together lets a single weak area colour the rest, which is the
    behaviour that made a single blended grade hard to act on. The calls run
    concurrently, so the extra cost is tokens rather than wall clock.

    `template` selects the prompt: the default fact template for criteria that
    describe expected content, `REQUIREMENT_TEMPLATE` for criteria that state a
    property the output must have.

    `calls_per_criterion` above 1 grades each criterion that many times and takes
    the median, which is worth paying for on a criterion whose graders disagree
    with themselves run to run. The default of 1 leaves existing callers exactly
    as they were.
    """
    if calls_per_criterion < 1:
        raise ValueError(
            f"calls_per_criterion must be at least 1, got {calls_per_criterion}"
        )

    rounds = await asyncio.gather(
        *(
            _grade_one(grader, criteria[key], answer, question, template)
            for key in keys
            for _ in range(calls_per_criterion)
        )
    )
    per_key = [
        rounds[i * calls_per_criterion : (i + 1) * calls_per_criterion]
        for i in range(len(keys))
    ]
    values = {
        key: statistics.median(value for value, _ in graded)
        for key, graded in zip(keys, per_key)
    }
    return Score(
        value=values,
        explanation="\n\n".join(
            f"### {key}: {values[key]}"
            + (
                f" (median of {len(graded)}: {[v for v, _ in graded]})"
                if len(graded) > 1
                else ""
            )
            + "\n"
            + "\n\n--- next grader call ---\n\n".join(r for _, r in graded)
            for key, graded in zip(keys, per_key)
        ),
    )


@metric
def applicable_mean() -> Metric:
    """Mean over the samples whose score says it applies to them.

    A scorer marks a score with ``metadata={"applicable": False}`` when the
    sample gives it nothing to judge; those are left out of the mean rather
    than padding it. With no applicable sample at all the metric is 0.0, which
    reads as a failure and so is noticed, rather than a silent perfect score.
    """

    to_float = value_to_float()

    def compute(scores: list[SampleScore]) -> float:
        applicable = [
            to_float(item.score.value)
            for item in scores
            if (item.score.metadata or {}).get("applicable", True)
        ]
        return statistics.mean(applicable) if applicable else 0.0

    return compute


@scorer(metrics=[applicable_mean()])
def tool_called(tool_name: str) -> Scorer:
    """CORRECT when the run's transcript shows the agent calling ``tool_name``.

    A behavioural check to sit next to the outcome scorers: a sample built so
    that the right answer is only reachable by using the tool can still be
    passed by a lucky guess, and a regression that stops the tool being called
    would then hide behind the outcome score. Only samples whose input embeds
    a figure (a local image reference) are judged; the rest score as not
    applicable. The metric is ``applicable_mean`` alone, so it is a plain rate
    over the figure samples with no stderr, and a text-only sample is left out
    rather than counted as a pass.
    """

    async def score(state: TaskState, target: Target) -> Score:
        if not references_local_images(state.input_text):
            return Score(
                value=CORRECT,
                explanation=f"Sample does not expect a {tool_name} call",
                metadata={"applicable": False},
            )
        calls = [
            call
            for message in state.messages
            if isinstance(message, ChatMessageAssistant) and message.tool_calls
            for call in message.tool_calls
            if call.function == tool_name
        ]
        if not calls:
            return Score(
                value=INCORRECT,
                explanation=f"{tool_name} was never called",
                metadata={"applicable": True},
            )
        arguments = "; ".join(str(call.arguments) for call in calls[:3])
        return Score(
            value=CORRECT,
            explanation=f"{tool_name} called {len(calls)} time(s): {arguments}",
            metadata={"applicable": True},
        )

    return score
