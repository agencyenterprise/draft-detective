/**
 * Utility functions for model comparison UI components
 */

import { ModelComparisonResult } from './types';

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
