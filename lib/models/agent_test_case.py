from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, TypedDict, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import LLMModel
from lib.models.agent import BaseAgent
from lib.models.comparison_models import FieldComparison

logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse", bound=BaseModel)


class EvaluationResult(BaseModel):
    """Result of evaluating agent output against expected output."""

    passed: bool = Field(description="Whether the expected and received results match")
    rationale: str = Field(description="Brief reason for the decision")
    field_comparisons: List[FieldComparison] = Field(
        default_factory=list, description="Detailed field-by-field comparison results"
    )


class AgentTestCase(BaseModel):
    """Test case for agents

    Architecture:
        - Test definition: name, agent, inputs, expected output
        - Comparison rules: strict/llm fields, ignore patterns
        - Execution state: model_results (populated by run())
        - Two methods: run(models) and compare_results()

    Usage:
        test_case = AgentTestCase(
            name="test_name",
            agent=my_agent,
            prompt_kwargs={"text": "..."},
            expected_dict={"claims": [...]},
            response_model=ClaimResult,
            strict_fields={"reference_index"},
            llm_fields={"claims"},
        )

        # Run with default model
        await test_case.run()
        result = await test_case.compare_results()
        assert result.passed

        # Or run with multiple models for comparison
        await test_case.run(models=[model1, model2, model3])
        result = await test_case.compare_results()  # Returns model1 (baseline)
        assert result.passed
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Class-level shared session ID for all test cases in a run
    _shared_session_id: Optional[str] = None

    # ===== Test Definition =====
    name: str = Field(description="Test case name")
    agent: BaseAgent = Field(description="Agent instance to test")
    response_model: Type[TResponse] = Field(description="Expected response model type")
    prompt_kwargs: Dict[str, Any] | BaseModel | TypedDict = Field(
        description="Agent invocation arguments"
    )
    expected_dict: Dict[str, Any] = Field(description="Expected output as dictionary")

    # ===== Comparison Rules =====
    strict_fields: set | dict = Field(
        default_factory=set,
        description="Fields to compare with exact matching",
    )
    llm_fields: set | dict = Field(
        default_factory=set,
        description="Fields to compare with LLM semantic evaluation",
    )
    ignore_fields: set | dict = Field(
        default_factory=set,
        description="Fields to exclude from all comparisons",
    )

    # ===== Configuration =====
    evaluator_model: str = Field(
        default="openai:gpt-5-mini",
        description="LLM model for semantic comparison (provider:model)",
    )
    fuzzy_threshold: float = Field(
        default=0.6,
        description="Minimum similarity score for fuzzy matches (0-1)",
    )
    good_match_threshold: float = Field(
        default=0.8,
        description="Score above which matches are considered excellent (0-1)",
    )
    llm_instructions: Optional[str] = Field(
        default=None,
        description="Special instructions for LLM-as-judge evaluation",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Langfuse session ID for tracing",
    )

    # ===== Execution State =====
    model_results: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Results from running agent(s), keyed by model name. Each result contains evaluation and metrics.",
    )

    # ===== Parsed Expected Output =====
    expected: Optional[TResponse] = Field(
        default=None,
        description="Parsed expected output (initialized from expected_dict)",
    )

    @classmethod
    def set_shared_session_id(cls, session_id: str):
        """Set a shared session ID for all test cases in this run."""
        cls._shared_session_id = session_id

    @classmethod
    def get_shared_session_id(cls) -> Optional[str]:
        """Get the shared session ID for all test cases."""
        return cls._shared_session_id

    def model_post_init(self, __context: Any) -> None:
        """Initialize parsed expected output and session ID."""
        if self.expected is None:
            self.expected = self.response_model.model_validate(self.expected_dict)

        if self.session_id is None:
            self.session_id = self._shared_session_id

    async def run(self, models: Optional[List[LLMModel]] = None) -> None:
        """Execute agent with specified model(s) and store results.

        This method runs the agent with one or more models in parallel and
        evaluates each output against the expected result. Results are stored
        in self.model_results for later retrieval.

        Args:
            models: List of models to test. Agent's default model is always
                    used as baseline (position 0). Duplicates are filtered.

        Side Effects:
            - Populates self.model_results with Dict[str, EvaluationResult]
            - Overwrites previous results if called multiple times

        Example:
            # Single model (default)
            await test_case.run()

            # Multiple models for comparison (default is always baseline)
            await test_case.run(models=[
                LLMModel.GPT_4,
                LLMModel.CLAUDE_3_5_SONNET,
                LLMModel.GEMINI_2_0_FLASH,
            ])
        """
        from lib.services.model_comparison import run_parallel_comparison

        # Default to agent's model if not specified
        if models is None:
            models_to_test = [self.agent.model]
        else:
            # Agent's default first, then others without duplicates
            default_model = self.agent.model
            models_to_test = [default_model] + [
                m for m in models if str(m) != str(default_model)
            ]

        logger.info(f"Running test '{self.name}' with {len(models_to_test)} model(s)")

        self.model_results = await run_parallel_comparison(self, models_to_test)

        logger.info(
            f"Test '{self.name}' completed: "
            f"{sum(1 for r in self.model_results.values() if r['passed'])}/{len(models_to_test)} models passed"
        )

    async def compare_results(self) -> EvaluationResult:
        """Retrieve baseline model's evaluation result.

        Returns the evaluation result for the first model in the list
        (the baseline model).

        Returns:
            EvaluationResult for the baseline model (first in models list)

        Raises:
            RuntimeError: If run() has not been called yet

        Example:
            await test_case.run(models=[baseline, model2, model3])
            result = await test_case.compare_results()  # Returns baseline's result
            assert result.passed, result.rationale
        """
        if self.model_results is None:
            raise RuntimeError(
                f"Test case '{self.name}': Must call run() before compare_results()"
            )

        if not self.model_results:
            raise RuntimeError(
                f"Test case '{self.name}': No results available after run()"
            )

        # Get first model's result (baseline)
        baseline_model = next(iter(self.model_results.keys()))
        baseline_data = self.model_results[baseline_model]

        # Reconstruct EvaluationResult from dict
        baseline_result = EvaluationResult(
            passed=baseline_data["passed"],
            rationale=baseline_data["rationale"],
            field_comparisons=baseline_data["field_comparisons"],
        )

        logger.debug(
            f"Test '{self.name}' baseline ({baseline_model}): "
            f"passed={baseline_result.passed}"
        )

        return baseline_result
