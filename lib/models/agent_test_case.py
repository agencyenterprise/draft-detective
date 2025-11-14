from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Protocol, Set, Type, TypeVar

from pydantic import BaseModel, Field, ConfigDict
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from deepdiff import DeepDiff


from lib.config.langfuse import langfuse_handler
from lib.models.agent import AgentProtocol
from lib.models.field_comparator import FieldComparator
from lib.models.comparison_models import FieldComparison


TResponse = TypeVar("TResponse", bound=BaseModel)


class EvaluationResult(BaseModel):
    passed: bool = Field(
        description="Whether the expected and received results match, thus passed the evaluation"
    )
    rationale: str = Field(description="Brief reason for the decision")
    field_comparisons: List[FieldComparison] = Field(
        default_factory=list, description="Detailed field-by-field comparison results"
    )


class AgentTestCase(BaseModel):
    """Generic container for agent test cases with mixed strict/LLM grading.

    - expected stores the golden output as a dict matching the agent's response model
    - expected/result are parsed instances of response_model for type-safe access
    - strict_fields are dotted selectors compared exactly (e.g., "reference_index")
    - llm_fields are field names to be graded by an LLM (e.g., "claims")
    - ignore_fields are dotted prefixes to omit from both expected and result prior to checks
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Class-level shared session ID for all test cases in a run
    _shared_session_id: Optional[str] = None

    name: str
    agent: AgentProtocol
    response_model: Type[TResponse]
    prompt_kwargs: Dict[str, Any]

    # Goldens and results
    expected_dict: Dict[str, Any]
    expected: Optional[TResponse] = None
    run_count: int = 1
    results: Optional[list[TResponse]] = None  # For multiple runs

    # Field selectors (same format as pydantic model_dump's include and exclude inputs)
    strict_fields: set | dict = Field(default_factory=set)
    llm_fields: set | dict = Field(default_factory=set)
    ignore_fields: set | dict = Field(default_factory=set)

    # Special instructions for LLM-as-a-judge evaluation
    llm_instructions: Optional[str] = Field(
        default=None,
        description="Special instructions to include in the LLM-as-a-judge prompt for semantic comparison",
    )

    # Evaluator model (provider:model) for LLM comparisons. Keep temperature 0 for determinism.
    evaluator_model: str = Field(default="openai:gpt-5-mini")

    fuzzy_threshold: float = Field(
        default=0.6, description="Minimum similarity score for fuzzy matches (0-1)"
    )
    good_match_threshold: float = Field(
        default=0.8,
        description="Score above which matches are considered excellent (0-1)",
    )

    # Stored intermediate eval results
    strict_eval_results: Optional[list[EvaluationResult]] = None
    llm_eval_results: Optional[list[EvaluationResult]] = None
    _eval_result: Optional[EvaluationResult] = None

    # Langfuse session information for this test run
    session_id: Optional[str] = None

    @classmethod
    def set_shared_session_id(cls, session_id: str):
        """Set a shared session ID for all test cases in this run."""
        cls._shared_session_id = session_id

    @classmethod
    def get_shared_session_id(cls) -> Optional[str]:
        """Get the shared session ID for all test cases."""
        return cls._shared_session_id

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        # Parse expected into the typed model instance
        if self.expected is None:
            self.expected = self.response_model.model_validate(self.expected_dict)  # type: ignore[arg-type]

        # Use shared session ID if instance session_id is not set
        if self.session_id is None:
            self.session_id = self._shared_session_id

    async def run(self) -> TResponse:
        """Run the agent and store the typed result."""

        tasks = [
            self.agent.ainvoke(
                self.prompt_kwargs,
                config={
                    "run_name": self.name,
                    "callbacks": [langfuse_handler],
                    "metadata": {
                        "langfuse_session_id": self.session_id,
                    },
                },
            )
            for _ in range(self.run_count)
        ]
        results = await asyncio.gather(*tasks)

        # Ensure result is the expected pydantic type
        self.results = [self.response_model.model_validate(result) for result in results]  # type: ignore[arg-type]
        return self.results  # type: ignore[return-value]

    async def _compare_llm_given_result(self, result: TResponse) -> EvaluationResult:
        """Use an LLM to semantically compare selected fields."""
        assert self.expected is not None and result is not None, "Run the test first"

        if len(self.llm_fields) == 0:
            return EvaluationResult(
                passed=True,
                rationale="No fields require llm comparison",
                field_comparisons=[],
            )

        expected_llm_json = self.expected.model_dump_json(
            include=self.llm_fields, exclude=self.ignore_fields, indent=2
        )
        result_llm_json = result.model_dump_json(
            include=self.llm_fields, exclude=self.ignore_fields, indent=2
        )

        if expected_llm_json == "{}" and result_llm_json == "{}":
            return EvaluationResult(
                passed=True,
                rationale="No fields require llm comparison",
                field_comparisons=[],
            )

        evaluator_model_str = str(self.evaluator_model)
        provider, model = evaluator_model_str.split(":", 1)
        grader = init_chat_model(
            model, model_provider=provider, temperature=0, timeout=180
        )
        grader = grader.with_structured_output(EvaluationResult)

        # Build base instructions
        base_instructions = """You are a strict evaluator for agent outputs.

Instructions:
- Compare the EXPECTED and RECEIVED JSON for the selected fields.
- For list-like fields, ignore order.
- For textual fields or rationales, accept minor wording differences if the meaning is equivalent.
- If counts differ in list-like fields or any expected item is missing semantically, return passed=False.

Return a boolean 'passed' (True if the expected and received results match, False otherwise) and a short 'rationale'."""

        # Append special instructions if provided
        if self.llm_instructions:
            instructions = f"{base_instructions}\n\nAdditional Instructions:\n{self.llm_instructions}"
        else:
            instructions = base_instructions

        prompt = ChatPromptTemplate.from_template(
            """{instructions}

EXPECTED JSON (selected fields):
```json
{expected_llm_json}
```

RECEIVED JSON (selected fields):
```json
{result_llm_json}
```
"""
        )

        messages = prompt.format_messages(
            instructions=instructions,
            expected_llm_json=expected_llm_json,
            result_llm_json=result_llm_json,
        )

        eval_result = await grader.ainvoke(
            messages,
            config={
                "run_name": f"{self.name}::llm_grader",
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_session_id": self.session_id,
                },
            },
        )

        # Add field-level comparisons for LLM fields using comparator
        comparator = FieldComparator(
            self.llm_fields,
            self.ignore_fields,
            fuzzy_threshold=self.fuzzy_threshold,
            good_match_threshold=self.good_match_threshold,
        )
        field_comparisons = comparator.compare_fields(
            self.expected, result, comparison_type="llm"
        )
        eval_result.field_comparisons = field_comparisons

        return eval_result

    async def _compare_strict_given_result(self, result: TResponse) -> EvaluationResult:
        assert self.expected is not None and result is not None, "Run the test first"

        if len(self.strict_fields) == 0:
            return EvaluationResult(
                passed=True,
                rationale="No strict fields to compare",
                field_comparisons=[],
            )

        # Use field comparator for detailed analysis
        comparator = FieldComparator(
            self.strict_fields,
            self.ignore_fields,
            fuzzy_threshold=self.fuzzy_threshold,
            good_match_threshold=self.good_match_threshold,
        )
        field_comparisons = comparator.compare_fields(
            self.expected, result, comparison_type="strict"
        )

        # Aggregate results
        all_passed = all(fc.passed for fc in field_comparisons)

        # Build summary rationale
        if all_passed:
            rationale = f"All {len(field_comparisons)} field(s) passed"
        else:
            failed_comps = [fc for fc in field_comparisons if not fc.passed]
            rationale_lines = ["Failed fields:"]
            for fc in failed_comps[:5]:
                rationale_lines.append(f"  • {fc.field_path}: {fc.rationale}")
            if len(failed_comps) > 5:
                rationale_lines.append(f"  ... and {len(failed_comps) - 5} more")
            rationale = "\n".join(rationale_lines)

        return EvaluationResult(
            passed=all_passed, rationale=rationale, field_comparisons=field_comparisons
        )

    async def prepare_aggregate_run_evaluation_result(
        self, eval_results: list[EvaluationResult], test_label: str | None = None
    ) -> EvaluationResult:
        num_passed = sum(1 for result in eval_results if result.passed)
        passed = num_passed == len(eval_results)
        pass_rate = num_passed / len(eval_results) * 100
        label_suffix = f" {test_label}" if test_label else ""
        rationale = f"{pass_rate:0.0f}% ({num_passed}/{len(eval_results)}) of runs passed{label_suffix}"

        if not passed:
            run_details = []
            for i, result in enumerate(eval_results):
                status = "✓" if result.passed else "✗"
                label = f" - {test_label}" if test_label else ""
                run_details.append(
                    f"{status} Run {i+1}/{self.run_count}{label}\n    ```\n    {result.rationale}\n    ```"
                )
            rationale += "\n" + "\n".join(run_details)

        # Aggregate field comparisons (use first run's comparisons as representative)
        field_comparisons = eval_results[0].field_comparisons if eval_results else []

        return EvaluationResult(
            passed=passed, rationale=rationale, field_comparisons=field_comparisons
        )

    async def _compare_llm(self) -> EvaluationResult:
        """Use an LLM to semantically compare selected fields."""
        assert (
            self.expected is not None and self.results is not None
        ), "Run the test first"

        if len(self.llm_fields) == 0:
            return EvaluationResult(
                passed=True, rationale="No fields require llm comparison"
            )

        tasks = [self._compare_llm_given_result(result) for result in self.results]
        self.llm_eval_results = await asyncio.gather(*tasks)
        return await self.prepare_aggregate_run_evaluation_result(
            self.llm_eval_results,
            "LLM Comparisons",
        )

    async def _compare_strict(self) -> EvaluationResult:
        assert (
            self.expected is not None and self.results is not None
        ), "Run the test first"

        if len(self.strict_fields) == 0:
            return EvaluationResult(
                passed=True, rationale="No strict fields to compare"
            )

        tasks = [self._compare_strict_given_result(result) for result in self.results]
        self.strict_eval_results = await asyncio.gather(*tasks)
        return await self.prepare_aggregate_run_evaluation_result(
            self.strict_eval_results,
            "Strict Comparisons",
        )

    async def compare_results(self) -> EvaluationResult:
        strict_eval = await self._compare_strict()
        llm_eval = await self._compare_llm()

        # Merge field comparisons from both evaluations
        all_field_comparisons = (
            strict_eval.field_comparisons + llm_eval.field_comparisons
        )

        eval_result = EvaluationResult(
            passed=strict_eval.passed and llm_eval.passed,
            rationale="\n".join([strict_eval.rationale, llm_eval.rationale]),
            field_comparisons=all_field_comparisons,
        )

        self._eval_result = eval_result

        return eval_result
