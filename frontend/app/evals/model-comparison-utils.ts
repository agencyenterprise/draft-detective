/**
 * Utility functions for model comparison UI components
 */

import { ModelComparisonResult, TestCase, EvaluationResult, ActualOutput } from './types';

/**
 * Result of getting display data for a test case
 */
export interface DisplayResults {
  evaluationResult: EvaluationResult;
  actualOutput: ActualOutput;
}

/**
 * Format model name by removing provider prefix
 */
export function formatModelName(modelName: string): string {
  return modelName.replace('openai:', '');
}

/**
 * Calculate cost difference as a percentage compared to baseline
 * Returns 0 for baseline model
 */
export function calculateCostDifference(currentCost: number, baselineCost: number, isBaseline: boolean): number {
  if (isBaseline) return 0;
  return ((currentCost - baselineCost) / baselineCost) * 100;
}

/**
 * Get baseline model from model comparison results
 * Returns the first model in the list
 */
export function getBaselineModel(modelComparisonResults: Record<string, ModelComparisonResult>): string | null {
  const models = Object.keys(modelComparisonResults);
  return models.length > 0 ? models[0] : null;
}

/**
 * Format cost difference with appropriate sign and color class
 */
export function formatCostDifference(costDiff: number): {
  sign: string;
  formatted: string;
  colorClass: string;
} {
  return {
    sign: costDiff > 0 ? '+' : '',
    formatted: `${costDiff.toFixed(1)}%`,
    colorClass: costDiff < 0 ? 'text-green-600' : 'text-red-600',
  };
}

/**
 * Calculate duration difference as a percentage compared to baseline
 * Returns 0 for baseline model
 */
export function calculateDurationDifference(
  currentDuration: number,
  baselineDuration: number,
  isBaseline: boolean,
): number {
  if (isBaseline) return 0;
  if (baselineDuration === 0) return 0;
  return ((currentDuration - baselineDuration) / baselineDuration) * 100;
}

/**
 * Format duration difference with appropriate sign and color class
 * Negative is better (faster), positive is worse (slower)
 */
export function formatDurationDifference(durationDiff: number): {
  sign: string;
  formatted: string;
  colorClass: string;
} {
  return {
    sign: durationDiff > 0 ? '+' : '',
    formatted: `${durationDiff.toFixed(1)}%`,
    colorClass: durationDiff < 0 ? 'text-green-600' : 'text-red-600',
  };
}

/**
 * Get display results for a test case based on selected model
 *
 * If a model is selected, returns that model's results.
 * Otherwise, returns the baseline (first model's) results or the default evaluation result.
 *
 * @param testCase - The test case to get results for
 * @param selectedModel - The currently selected model name (optional)
 * @returns Display results containing evaluation and actual output
 */
export function getDisplayResults(testCase: TestCase, selectedModel: string | null): DisplayResults {
  // Default to baseline (first model or no comparison)
  if (!selectedModel || !testCase.agent_test_case.model_comparison_results) {
    // Get baseline model's actual output
    const baselineModelName = testCase.agent_test_case.model_comparison_results
      ? Object.keys(testCase.agent_test_case.model_comparison_results)[0]
      : null;

    const actualOutput =
      baselineModelName && testCase.agent_test_case.model_comparison_results?.[baselineModelName]?.actual_output
        ? testCase.agent_test_case.model_comparison_results[baselineModelName].actual_output
        : testCase.agent_test_case.actual_outputs[0] || testCase.agent_test_case.expected_output;

    return {
      evaluationResult: testCase.agent_test_case.evaluation_result,
      actualOutput,
    };
  }

  const modelResult = testCase.agent_test_case.model_comparison_results[selectedModel];

  if (!modelResult) {
    return {
      evaluationResult: testCase.agent_test_case.evaluation_result,
      actualOutput: testCase.agent_test_case.actual_outputs[0] || testCase.agent_test_case.expected_output,
    };
  }

  return {
    evaluationResult: {
      passed: modelResult.passed,
      rationale: modelResult.rationale,
      field_comparisons: modelResult.field_comparisons,
    },
    // Use the selected model's actual output
    actualOutput: modelResult.actual_output || testCase.agent_test_case.expected_output,
  };
}
