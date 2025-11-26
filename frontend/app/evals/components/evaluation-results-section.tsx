import { Badge } from '@/components/ui/badge';
import { TestCase } from '../types';
import { formatModelName, DisplayResults } from '../model-comparison-utils';

interface EvaluationResultsSectionProps {
  testCases: TestCase[];
  selectedModel: string | null;
  getDisplayResults: (testCase: TestCase) => DisplayResults;
}

export function EvaluationResultsSection({
  testCases,
  selectedModel,
  getDisplayResults,
}: EvaluationResultsSectionProps) {
  return (
    <div className="border-t pt-4">
      <h4 className="font-medium mb-3 flex items-center gap-2">
        Evaluation Results
        {selectedModel && (
          <Badge variant="secondary" className="text-xs">
            for {formatModelName(selectedModel)}
          </Badge>
        )}
      </h4>
      {testCases.map((testCase, index) => {
        const { evaluationResult } = getDisplayResults(testCase);

        return (
          <div key={testCase.nodeid} className="mb-4">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">
                {selectedModel ? `${formatModelName(selectedModel)} Result` : `Overall Result`} #{index + 1}:
              </span>
              <Badge variant={evaluationResult.passed ? 'success' : 'destructive'}>
                {evaluationResult.passed ? 'Passed' : 'Failed'}
              </Badge>
            </div>
            <div className="text-sm text-muted-foreground mt-1 bg-background p-2 rounded border max-h-64 overflow-y-auto whitespace-pre-wrap font-mono">
              {evaluationResult.rationale}
            </div>
          </div>
        );
      })}
    </div>
  );
}
