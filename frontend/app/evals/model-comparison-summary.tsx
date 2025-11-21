import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { TrendingDown, TrendingUp, Zap, Info, TriangleAlert } from 'lucide-react';
import { TestCase } from './types';
import {
  formatModelName,
  calculateCostDifference,
  formatCostDifference,
  calculateDurationDifference,
  formatDurationDifference,
} from './model-comparison-utils';

interface ModelComparisonSummaryProps {
  testCases: TestCase[];
}

interface ModelMetrics {
  totalTests: number;
  passed: number;
  failed: number;
  passRate: number;
  totalCost: number;
  avgCost: number;
  totalTokens: number;
  avgTokens: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalDuration: number;
  avgDuration: number;
}

function aggregateModelMetrics(testCases: TestCase[]): Record<string, ModelMetrics> | null {
  const modelMetrics: Record<string, ModelMetrics> = {};

  const hasModelComparison = testCases.some((tc) => tc.agent_test_case.model_comparison_results);

  if (!hasModelComparison) {
    return null;
  }

  testCases.forEach((testCase) => {
    const results = testCase.agent_test_case.model_comparison_results;
    if (!results) return;

    Object.entries(results).forEach(([modelName, result]) => {
      if (!modelMetrics[modelName]) {
        modelMetrics[modelName] = {
          totalTests: 0,
          passed: 0,
          failed: 0,
          passRate: 0,
          totalCost: 0,
          avgCost: 0,
          totalTokens: 0,
          avgTokens: 0,
          totalInputTokens: 0,
          totalOutputTokens: 0,
          totalDuration: 0,
          avgDuration: 0,
        };
      }

      const metrics = modelMetrics[modelName];
      metrics.totalTests += 1;
      if (result.passed) {
        metrics.passed += 1;
      } else {
        metrics.failed += 1;
      }
      metrics.totalCost += result.cost_usd || 0;
      metrics.totalTokens += result.total_tokens || 0;
      metrics.totalInputTokens += result.input_tokens || 0;
      metrics.totalOutputTokens += result.output_tokens || 0;
      metrics.totalDuration += result.duration_seconds || 0;
    });
  });

  Object.values(modelMetrics).forEach((metrics) => {
    metrics.passRate = (metrics.passed / metrics.totalTests) * 100;
    metrics.avgCost = metrics.totalCost / metrics.totalTests;
    metrics.avgTokens = metrics.totalTokens / metrics.totalTests;
    metrics.avgDuration = metrics.totalDuration / metrics.totalTests;
  });

  return modelMetrics;
}

export function ModelComparisonSummary({ testCases }: ModelComparisonSummaryProps) {
  const modelMetrics = aggregateModelMetrics(testCases);

  if (!modelMetrics) {
    return null;
  }

  const models = Object.keys(modelMetrics);
  if (models.length === 0) {
    return null;
  }

  const baselineModel = models[0];
  const baselineMetrics = modelMetrics[baselineModel];

  const bestModel = models.reduce((best, current) => {
    const currentMetrics = modelMetrics[current];
    const bestMetrics = modelMetrics[best];

    if (currentMetrics.passRate > bestMetrics.passRate) return current;
    if (currentMetrics.passRate === bestMetrics.passRate && currentMetrics.avgCost < bestMetrics.avgCost)
      return current;
    return best;
  }, baselineModel);

  return (
    <div className="border-t pt-4 mt-4">
      <div className="flex items-center gap-2 mb-3">
        <Zap className="h-4 w-4 text-amber-500" />
        <h4 className="font-medium">Model Comparison Summary</h4>
        <Badge variant="outline" className="text-xs">
          {models.length} models · {baselineMetrics.totalTests} test cases
        </Badge>
      </div>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead className="text-center">Pass Rate</TableHead>
              <TableHead className="text-right">Avg Latency</TableHead>
              <TableHead className="text-right">Latency vs Baseline</TableHead>
              <TableHead className="text-right">Avg Cost</TableHead>
              <TableHead className="text-right">Cost vs Baseline</TableHead>
              <TableHead className="text-right">Avg Tokens</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((modelName) => {
              const metrics = modelMetrics[modelName];
              const isBaseline = modelName === baselineModel;
              const isBest = modelName === bestModel;
              const costDiff = calculateCostDifference(metrics.avgCost, baselineMetrics.avgCost, isBaseline);
              const costDiffFormatted = formatCostDifference(costDiff);
              const durationDiff = calculateDurationDifference(
                metrics.avgDuration,
                baselineMetrics.avgDuration,
                isBaseline,
              );
              const durationDiffFormatted = formatDurationDifference(durationDiff);

              return (
                <TableRow key={modelName} className={isBaseline ? 'bg-muted/30' : ''}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {formatModelName(modelName)}
                      {isBaseline && (
                        <Badge variant="secondary" className="text-xs">
                          baseline
                        </Badge>
                      )}
                      {isBest && !isBaseline && metrics.passRate >= 95 && (
                        <Badge variant="default" className="text-xs bg-green-600">
                          recommended
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-2">
                      {metrics.passRate < 70 && <TriangleAlert className="h-3 w-3 text-yellow-600" />}
                      <span className="font-mono text-sm">{metrics.passRate.toFixed(1)}%</span>
                      <span className="text-xs text-muted-foreground">
                        ({metrics.passed}/{metrics.totalTests})
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">{metrics.avgDuration.toFixed(2)}s</TableCell>
                  <TableCell className="text-right">
                    {isBaseline ? (
                      <span className="text-muted-foreground text-xs">-</span>
                    ) : (
                      <div className="flex items-center justify-end gap-1">
                        {durationDiff < 0 ? (
                          <TrendingDown className="h-3 w-3 text-green-600" />
                        ) : (
                          <TrendingUp className="h-3 w-3 text-red-600" />
                        )}
                        <span className={`text-xs font-medium ${durationDiffFormatted.colorClass}`}>
                          {durationDiffFormatted.sign}
                          {durationDiffFormatted.formatted}
                        </span>
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">${metrics.avgCost.toFixed(4)}</TableCell>
                  <TableCell className="text-right">
                    {isBaseline ? (
                      <span className="text-muted-foreground text-xs">-</span>
                    ) : (
                      <div className="flex items-center justify-end gap-1">
                        {costDiff < 0 ? (
                          <TrendingDown className="h-3 w-3 text-green-600" />
                        ) : (
                          <TrendingUp className="h-3 w-3 text-red-600" />
                        )}
                        <span className={`text-xs font-medium ${costDiffFormatted.colorClass}`}>
                          {costDiffFormatted.sign}
                          {costDiffFormatted.formatted}
                        </span>
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {(Math.round(metrics.avgTokens) || 0).toLocaleString()}
                    <div className="text-xs text-muted-foreground">
                      {Math.round(metrics.totalInputTokens / metrics.totalTests) || 0}in ·{' '}
                      {Math.round(metrics.totalOutputTokens / metrics.totalTests) || 0}out
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-4 w-4 cursor-help" />
          </TooltipTrigger>
          <TooltipContent>
            <p>Token counts and costs from actual OpenAI API responses</p>
            <p className="mt-1">All metrics are real usage data, not estimates</p>
          </TooltipContent>
        </Tooltip>
        <span>Real API Data</span>
      </div>
    </div>
  );
}
