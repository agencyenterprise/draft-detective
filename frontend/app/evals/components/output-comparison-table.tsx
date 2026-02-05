import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TestCase } from '../types';
import { getFlattenedObjectValue } from '../util';
import { cn } from '@/lib/utils';
import { formatModelName, DisplayResults } from '../model-comparison-utils';

interface OutputComparisonTableProps {
  testCases: TestCase[];
  allKeys: string[];
  selectedModel: string | null;
  getDisplayResults: (testCase: TestCase) => DisplayResults;
}

export function OutputComparisonTable({
  testCases,
  allKeys,
  selectedModel,
  getDisplayResults,
}: OutputComparisonTableProps) {
  if (!testCases.length || !testCases[0]?.agent_test_case) {
    return (
      <div className="border-t pt-4">
        <p className="text-sm text-muted-foreground">No test case data available</p>
      </div>
    );
  }

  return (
    <div className="border-t pt-4">
      <h4 className="font-medium mb-3 flex items-center gap-2">
        Full Output Comparison
        {selectedModel && (
          <Badge variant="secondary" className="text-xs">
            showing {formatModelName(selectedModel)}
          </Badge>
        )}
      </h4>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-left p-3 font-medium text-sm">Field</TableHead>
              <TableHead className="text-left p-3 font-medium text-sm">Expected</TableHead>
              {testCases.map((testCase, index) => {
                const { evaluationResult } = getDisplayResults(testCase);
                return (
                  <TableHead key={testCase.nodeid} className="text-left p-3 font-medium text-sm">
                    <p className="flex items-center gap-1">
                      <span>
                        {selectedModel ? `${formatModelName(selectedModel)} #${index + 1}` : `Actual #${index + 1}`}
                      </span>
                      <span
                        className={cn(
                          'text-xs px-1 py-0.5 w-12 text-center rounded-md',
                          evaluationResult.passed ? 'text-green-600 bg-green-500/10' : 'text-red-600 bg-red-500/10',
                        )}
                      >
                        {evaluationResult.passed ? 'Passed' : 'Failed'}
                      </span>
                    </p>
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {allKeys.map((key) => {
              const expectedValue = getFlattenedObjectValue(testCases[0].agent_test_case.expected_output, key);

              return (
                <TableRow key={key}>
                  <TableCell className="font-mono text-xs wrap-anywhere align-top">{key}</TableCell>
                  <TableCell className="wrap-anywhere align-top min-w-80">
                    {expectedValue !== undefined ? (
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">{String(expectedValue)}</p>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">Not specified</span>
                    )}
                  </TableCell>
                  {testCases.map((testCase) => {
                    const { actualOutput } = getDisplayResults(testCase);
                    const actualValue = getFlattenedObjectValue(actualOutput, key);

                    return (
                      <TableCell key={testCase.nodeid} className="wrap-anywhere align-top min-w-80">
                        {actualValue !== undefined ? (
                          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{String(actualValue)}</p>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Not provided</span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
