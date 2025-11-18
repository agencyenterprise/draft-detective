"""Service for running model comparison tests."""

import logging
import time
from typing import Dict, List

from lib.models.agent_test_case import AgentTestCase, EvaluationResult
from lib.models.agent_with_model_override import create_agent_with_model
from lib.services.langfuse_metrics import calculate_metrics
from lib.config.llm_models import LLMModel

logger = logging.getLogger(__name__)


class ModelComparisonRunner:
    """Handles running model comparison tests."""

    @staticmethod
    async def run_with_model_comparison(
        test_case: AgentTestCase, comparison_models: List[LLMModel]
    ) -> Dict[str, EvaluationResult]:
        """Run the test case with multiple models and compare results.

        Args:
            test_case: The test case to run
            comparison_models: List of models to test (including baseline)

        Returns:
            Dictionary mapping model names to their evaluation results
        """
        results = {}
        model_metrics = {}
        original_agent = test_case.agent

        for model in comparison_models:
            test_agent = create_agent_with_model(original_agent, model)
            test_case.agent = test_agent
            test_case.results = None

            start_time = time.time()
            await test_case.run()
            eval_result = await test_case.compare_results()
            execution_time = time.time() - start_time

            usage = test_agent.get_last_usage()
            model_name = str(model)
            
            metrics = calculate_metrics(
                model_name=model_name,
                execution_time=execution_time,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

            logger.info(
                f"Model {model} metrics for {test_case.name}: "
                f"cost=${metrics.cost_usd:.4f}, duration={metrics.duration_seconds:.2f}s, "
                f"tokens={metrics.total_tokens} (in:{metrics.input_tokens}, out:{metrics.output_tokens})"
            )

            results[model_name] = eval_result
            model_metrics[model_name] = metrics.model_dump()

        test_case.agent = original_agent

        test_case.model_comparison_results = {
            model_name: {
                "passed": eval_result.passed,
                "rationale": eval_result.rationale,
                "field_comparisons": [
                    fc.model_dump() for fc in eval_result.field_comparisons
                ],
                **model_metrics[model_name],
            }
            for model_name, eval_result in results.items()
        }

        return results
