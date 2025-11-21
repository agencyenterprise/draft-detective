"""Parallel model comparison orchestrator for agent test cases.

This service coordinates parallel execution of agent tests across multiple models,
collecting evaluation results and metrics for comparison.
"""

import asyncio
import logging
from typing import Any, Dict, List, TYPE_CHECKING

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

from lib.config.langfuse import langfuse_handler
from lib.config.llm_models import LLMModel
from lib.models.agent import BaseAgent
from lib.models.field_comparator import FieldComparator
from lib.services.agent_factory import create_agent_with_model
from lib.services.agent_tracking import AgentExecutionTracker

if TYPE_CHECKING:
    from lib.models.agent_test_case import AgentTestCase, EvaluationResult
    from lib.services.langfuse_metrics import ModelMetrics
    from lib.models.comparison_models import FieldComparison

logger = logging.getLogger(__name__)


async def run_single_model_evaluation(
    test_case: "AgentTestCase",
    agent: BaseAgent,
    tracker: AgentExecutionTracker,
) -> tuple["EvaluationResult", "ModelMetrics", Any]:
    """Run agent with single model and return evaluation with metrics and actual output.

    Args:
        test_case: The test case to run
        agent: Agent instance configured for a specific model
        tracker: Execution tracker for this run

    Returns:
        Tuple of (EvaluationResult, ModelMetrics, actual_output) with evaluation, metrics, and the actual model output
    """
    from lib.models.agent_test_case import EvaluationResult
    from lib.services.langfuse_metrics import ModelMetrics

    tracker.start_timing()

    config = {
        "run_name": test_case.name,
        "callbacks": tracker.get_callbacks(),
        "metadata": {
            "langfuse_session_id": test_case.session_id,
        },
    }

    result = await agent.ainvoke(test_case.prompt_kwargs, config=config)

    tracker.stop_timing()
    tracker.update_langfuse_costs()

    metrics = tracker.get_metrics()

    validated_result = test_case.response_model.model_validate(result)

    eval_result = await evaluate_agent_output(
        test_case=test_case,
        actual_output=validated_result,
    )

    logger.info(
        f"Model {agent.model} completed '{test_case.name}': "
        f"passed={eval_result.passed}, "
        f"cost=${metrics.cost_usd:.4f}, "
        f"duration={metrics.duration_seconds:.2f}s, "
        f"tokens={metrics.total_tokens}"
    )

    return eval_result, metrics, validated_result


def _create_field_comparator(
    test_case: "AgentTestCase",
    fields: set | dict,
) -> FieldComparator:
    """Create field comparator with test case configuration.

    Args:
        test_case: Test case with comparison configuration
        fields: Fields to compare

    Returns:
        Configured FieldComparator instance
    """
    return FieldComparator(
        fields,
        test_case.ignore_fields,
        fuzzy_threshold=test_case.fuzzy_threshold,
        good_match_threshold=test_case.good_match_threshold,
    )


def _build_rationale(
    field_comparisons: List["FieldComparison"],
    field_type: str,
) -> str:
    """Build rationale message from field comparisons.

    Args:
        field_comparisons: List of field comparison results
        field_type: Type of fields being compared (e.g., "strict", "LLM")

    Returns:
        Formatted rationale string
    """
    all_passed = all(fc.passed for fc in field_comparisons)

    if all_passed:
        return f"✓ All {len(field_comparisons)} {field_type} field(s) passed"

    failed_comps = [fc for fc in field_comparisons if not fc.passed]
    rationale_lines = [f"✗ {len(failed_comps)} {field_type} field(s) failed:"]
    for fc in failed_comps[:5]:
        rationale_lines.append(f"  • {fc.field_path}: {fc.rationale}")
    if len(failed_comps) > 5:
        rationale_lines.append(f"  ... and {len(failed_comps) - 5} more")
    return "\n".join(rationale_lines)


async def evaluate_agent_output(
    test_case: "AgentTestCase",
    actual_output: Any,
) -> "EvaluationResult":
    """Evaluate actual agent output against expected output.

    Performs both strict and LLM-based comparison according to test case configuration.

    Args:
        test_case: Test case with expected output and comparison rules
        actual_output: Actual agent output to evaluate

    Returns:
        EvaluationResult combining strict and LLM evaluations
    """
    from lib.models.agent_test_case import EvaluationResult

    strict_result, llm_result = await asyncio.gather(
        _compare_strict_fields(test_case, actual_output),
        _compare_llm_fields(test_case, actual_output),
    )

    all_passed = strict_result.passed and llm_result.passed
    combined_rationale = "\n".join(
        [
            strict_result.rationale,
            llm_result.rationale,
        ]
    )
    combined_field_comparisons = (
        strict_result.field_comparisons + llm_result.field_comparisons
    )

    return EvaluationResult(
        passed=all_passed,
        rationale=combined_rationale,
        field_comparisons=combined_field_comparisons,
    )


async def _compare_strict_fields(
    test_case: "AgentTestCase",
    actual_output: Any,
) -> "EvaluationResult":
    """Compare strict fields using exact matching.

    Args:
        test_case: Test case with comparison configuration
        actual_output: Actual agent output to compare

    Returns:
        EvaluationResult with strict field comparison results
    """
    from lib.models.agent_test_case import EvaluationResult

    if len(test_case.strict_fields) == 0:
        return EvaluationResult(
            passed=True,
            rationale="No strict fields to compare",
            field_comparisons=[],
        )

    comparator = _create_field_comparator(test_case, test_case.strict_fields)
    field_comparisons = comparator.compare_fields(
        test_case.expected, actual_output, comparison_type="strict"
    )

    all_passed = all(fc.passed for fc in field_comparisons)
    rationale = _build_rationale(field_comparisons, "strict")

    return EvaluationResult(
        passed=all_passed,
        rationale=rationale,
        field_comparisons=field_comparisons,
    )


def _prepare_llm_comparison_data(
    test_case: "AgentTestCase",
    actual_output: Any,
) -> tuple[str, str]:
    """Prepare JSON data for LLM comparison.

    Args:
        test_case: Test case with expected output
        actual_output: Actual agent output

    Returns:
        Tuple of (expected_json, actual_json) as formatted strings
    """
    expected_json = test_case.expected.model_dump_json(
        include=test_case.llm_fields,
        exclude=test_case.ignore_fields,
        indent=2,
    )
    actual_json = actual_output.model_dump_json(
        include=test_case.llm_fields,
        exclude=test_case.ignore_fields,
        indent=2,
    )
    return expected_json, actual_json


def _build_llm_evaluation_instructions(
    test_case: "AgentTestCase",
) -> str:
    """Build instructions for LLM evaluator.

    Args:
        test_case: Test case with optional custom instructions

    Returns:
        Complete instruction string for LLM evaluator
    """
    base_instructions = """You are a strict evaluator for agent outputs.

Instructions:
- Compare the EXPECTED and RECEIVED JSON for the selected fields.
- For list-like fields, ignore order.
- For textual fields or rationales, accept minor wording differences if the meaning is equivalent.
- If counts differ in list-like fields or any expected item is missing semantically, return passed=False.

Return a boolean 'passed' (True if the expected and received results match, False otherwise) and a short 'rationale'."""

    if test_case.llm_instructions:
        return f"{base_instructions}\n\nAdditional Instructions:\n{test_case.llm_instructions}"
    return base_instructions


async def _invoke_llm_evaluator(
    test_case: "AgentTestCase",
    expected_json: str,
    actual_json: str,
) -> "EvaluationResult":
    """Invoke LLM to evaluate outputs.

    Args:
        test_case: Test case with evaluator configuration
        expected_json: Expected output as JSON string
        actual_json: Actual output as JSON string

    Returns:
        EvaluationResult from LLM grader
    """
    from lib.models.agent_test_case import EvaluationResult

    evaluator_model_str = str(test_case.evaluator_model)
    provider, model = evaluator_model_str.split(":", 1)
    grader = init_chat_model(model, model_provider=provider, temperature=0, timeout=180)
    grader = grader.with_structured_output(EvaluationResult)

    instructions = _build_llm_evaluation_instructions(test_case)

    prompt = ChatPromptTemplate.from_template(
        """{instructions}

EXPECTED JSON (selected fields):
```json
{expected_json}
```

RECEIVED JSON (selected fields):
```json
{actual_json}
```
"""
    )

    messages = prompt.format_messages(
        instructions=instructions,
        expected_json=expected_json,
        actual_json=actual_json,
    )

    eval_result = await grader.ainvoke(
        messages,
        config={
            "run_name": f"{test_case.name}::llm_grader",
            "callbacks": [langfuse_handler],
            "metadata": {
                "langfuse_session_id": test_case.session_id,
            },
        },
    )

    return eval_result


async def _compare_llm_fields(
    test_case: "AgentTestCase",
    actual_output: Any,
) -> "EvaluationResult":
    """Compare LLM fields using semantic evaluation.

    Args:
        test_case: Test case with comparison configuration
        actual_output: Actual agent output to compare

    Returns:
        EvaluationResult with LLM field comparison results
    """
    from lib.models.agent_test_case import EvaluationResult

    if len(test_case.llm_fields) == 0:
        return EvaluationResult(
            passed=True,
            rationale="No LLM fields to compare",
            field_comparisons=[],
        )

    expected_json, actual_json = _prepare_llm_comparison_data(test_case, actual_output)

    if expected_json == "{}" and actual_json == "{}":
        return EvaluationResult(
            passed=True,
            rationale="No LLM fields to compare",
            field_comparisons=[],
        )

    eval_result = await _invoke_llm_evaluator(test_case, expected_json, actual_json)

    comparator = _create_field_comparator(test_case, test_case.llm_fields)
    field_comparisons = comparator.compare_fields(
        test_case.expected, actual_output, comparison_type="llm"
    )
    eval_result.field_comparisons = field_comparisons

    prefix = "✓" if eval_result.passed else "✗"
    eval_result.rationale = f"{prefix} LLM evaluation: {eval_result.rationale}"

    return eval_result


async def run_parallel_comparison(
    test_case: "AgentTestCase",
    models: list[LLMModel],
) -> Dict[str, Dict[str, Any]]:
    """Run test case with multiple models in parallel.

    Creates agent variants for each model, executes them in parallel using
    asyncio.gather, and returns evaluation results with metrics keyed by model name.

    Args:
        test_case: The test case to run
        models: List of models to test (first is baseline)

    Returns:
        Dictionary mapping model names to result dictionaries containing:
        - passed: bool
        - rationale: str
        - field_comparisons: list[FieldComparison]
        - cost_usd: float
        - duration_seconds: float
        - input_tokens: int
        - output_tokens: int
        - total_tokens: int

    Raises:
        ValueError: If models list is empty
    """
    from lib.models.agent_test_case import EvaluationResult

    if not models:
        raise ValueError("Must provide at least one model")

    logger.info(
        f"Running parallel comparison for '{test_case.name}' with {len(models)} model(s)"
    )

    agents_and_trackers = [
        (create_agent_with_model(test_case.agent, model), AgentExecutionTracker(model))
        for model in models
    ]

    tasks = [
        run_single_model_evaluation(test_case, agent, tracker)
        for agent, tracker in agents_and_trackers
    ]

    results = await asyncio.gather(*tasks)

    model_results = {}
    for model, (eval_result, metrics, actual_output) in zip(models, results):
        model_name = str(model)
        model_results[model_name] = {
            "passed": eval_result.passed,
            "rationale": eval_result.rationale,
            "field_comparisons": eval_result.field_comparisons,
            "cost_usd": metrics.cost_usd,
            "duration_seconds": metrics.duration_seconds,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "total_tokens": metrics.total_tokens,
            "actual_output": (
                actual_output.model_dump()
                if hasattr(actual_output, "model_dump")
                else actual_output
            ),
        }

    # Log summary
    passed_count = sum(1 for eval_result, _, _ in results if eval_result.passed)
    logger.info(
        f"Parallel comparison complete for '{test_case.name}': "
        f"{passed_count}/{len(models)} models passed"
    )

    return model_results
