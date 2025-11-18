import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { CheckCircle2, XCircle, TrendingDown, TrendingUp, Info } from 'lucide-react';
import { ModelComparisonResult } from './types';
import { formatModelName, calculateCostDifference, formatCostDifference } from './model-comparison-utils';
import { cn } from '@/lib/utils';

interface ModelComparisonSectionProps {
  modelComparisonResults: Record<string, ModelComparisonResult>;
  selectedModel?: string;
  onModelSelect?: (modelName: string) => void;
}

export function ModelComparisonSection({
  modelComparisonResults,
  selectedModel,
  onModelSelect,
}: ModelComparisonSectionProps) {
  const models = Object.keys(modelComparisonResults);

  if (models.length === 0) {
    return null;
  }

  // First model is baseline
  const baselineModel = models[0];
  const baselineResult = modelComparisonResults[baselineModel];

  return (
    <div className="border-t pt-4 mt-4">
      <h4 className="font-medium mb-3 flex items-center gap-2">
        <span>Model Comparison Results</span>
        <Badge variant="outline" className="text-xs">
          {models.length} models tested
        </Badge>
        {selectedModel && (
          <Badge variant="secondary" className="text-xs">
            Viewing: {formatModelName(selectedModel)}
          </Badge>
        )}
      </h4>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Result</TableHead>
              <TableHead className="text-right">Tokens</TableHead>
              <TableHead className="text-right">Input</TableHead>
              <TableHead className="text-right">Output</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">vs Baseline</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((modelName) => {
              const result = modelComparisonResults[modelName];
              const isBaseline = modelName === baselineModel;
              const isSelected = selectedModel === modelName;
              const costDiff = calculateCostDifference(result.cost_usd, baselineResult.cost_usd, isBaseline);
              const costDiffFormatted = formatCostDifference(costDiff);

              return (
                <TableRow
                  key={modelName}
                  className={cn(
                    'cursor-pointer transition-colors hover:bg-muted/50',
                    isBaseline && 'bg-muted/30',
                    isSelected && 'bg-blue-50 dark:bg-blue-950/30 border-l-2 border-l-blue-500',
                  )}
                  onClick={() => onModelSelect?.(modelName)}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {formatModelName(modelName)}
                      {isBaseline && (
                        <Badge variant="secondary" className="text-xs">
                          baseline
                        </Badge>
                      )}
                      {isSelected && (
                        <Badge variant="outline" className="text-xs border-blue-500 text-blue-700 dark:text-blue-300">
                          viewing
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {result.passed ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-600" />
                      )}
                      <Badge variant={result.passed ? 'success' : 'destructive'} className="text-xs">
                        {result.passed ? 'Passed' : 'Failed'}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {(result.total_tokens ?? 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">
                    {(result.input_tokens ?? 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">
                    {(result.output_tokens ?? 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">${result.cost_usd.toFixed(4)}</TableCell>
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
            <p>Click on a model row to view its specific evaluation results</p>
            <p className="mt-1">Token counts and costs from actual API responses</p>
            <p className="mt-1">All metrics are real usage data, not estimates</p>
          </TooltipContent>
        </Tooltip>
        <span>Click a model to view its results • Real API Data</span>
      </div>
    </div>
  );
}
