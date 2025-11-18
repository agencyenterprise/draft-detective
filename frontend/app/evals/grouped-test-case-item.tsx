'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { ChevronDown, ChevronRight, Clock } from 'lucide-react';
import { useState } from 'react';
import { TestCase } from './types';
import { formatDuration, formatIncEx, getFlattenedObjectKeys, getFlattenedObjectValue } from './util';
import { cn } from '@/lib/utils';
import { percentageFormatter } from './formatters';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ModelComparisonSection } from './model-comparison-section';
import { formatModelName } from './model-comparison-utils';

interface GroupedTestCaseItem {
  name: string;
  testCases: TestCase[];
  consistencyProbability: number;
}

export function GroupedTestCaseItem({ name, testCases }: GroupedTestCaseItem) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleModelSelect = (modelName: string) => {
    setSelectedModel(modelName);
  };

  const passedTests = testCases.filter((testCase) => testCase.outcome === 'passed');
  const accuracy = passedTests.length / testCases.length;

  const hasModelComparison = testCases[0]?.agent_test_case.model_comparison_results;

  const getDisplayResults = (testCase: TestCase) => {
    if (!selectedModel || !testCase.agent_test_case.model_comparison_results) {
      return {
        evaluationResult: testCase.agent_test_case.evaluation_result,
      };
    }

    const modelResult = testCase.agent_test_case.model_comparison_results[selectedModel];

    if (!modelResult) {
      return {
        evaluationResult: testCase.agent_test_case.evaluation_result,
      };
    }

    return {
      evaluationResult: {
        passed: modelResult.passed,
        rationale: modelResult.rationale,
        field_comparisons: modelResult.field_comparisons,
      },
    };
  };

  const expectedKeys = getFlattenedObjectKeys(testCases[0].agent_test_case.expected_output);
  const actualKeys = getFlattenedObjectKeys(testCases[0].agent_test_case.actual_outputs[0]);
  const allKeys = [...new Set([...expectedKeys, ...actualKeys])].sort((a, b) => a.localeCompare(b));

  return (
    <Card className="py-1">
      <div className="cursor-pointer px-4 py-2" onClick={toggleExpanded}>
        <div className="space-y-2">
          <div className="flex items-center gap-2 justify-between">
            <div className="flex items-center gap-2 ">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <p className="text-sm font-medium flex items-center gap-2">{name}</p>
            </div>
            <Badge
              variant={accuracy >= 0.8 ? 'success' : accuracy >= 0.6 ? 'secondary' : 'destructive'}
              className="self-end"
            >
              {percentageFormatter.format(accuracy)} accuracy
            </Badge>
          </div>

          <div className="space-y-2 pl-6">
            {testCases.map((testCase) => (
              <div key={testCase.nodeid} className="flex gap-1 items-center">
                <p className="text-xs text-muted-foreground wrap-anywhere">{testCase.nodeid}</p>
                <span
                  className={cn(
                    'text-xs px-1 py-0.5 w-12 text-center rounded-md',
                    testCase.outcome === 'passed' ? 'text-green-600 bg-green-500/10' : 'text-red-600 bg-red-500/10',
                  )}
                >
                  {testCase.outcome === 'passed' ? 'Passed' : 'Failed'}
                </span>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {formatDuration(testCase.call.duration)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-6">
            {/* Test Configuration */}
            <div>
              <h4 className="font-medium mb-3">Test Configuration</h4>
              <div className="bg-muted/30 p-3 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="font-medium text-sm">Agent:</span>
                      <span className="text-sm text-muted-foreground">{testCases[0].agent_test_case.agent.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium text-sm">Run Count:</span>
                      <span className="text-sm text-muted-foreground">
                        {testCases[0].agent_test_case.evaluation_config.run_count}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium text-sm">Evaluator Model:</span>
                      <span className="text-sm text-muted-foreground">
                        {testCases[0].agent_test_case.evaluation_config.evaluator_model}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <span className="font-medium text-sm">Strict Fields:</span>
                      <div className="mt-1 text-sm text-muted-foreground wrap-break-word bg-background p-2 rounded border max-h-32 overflow-y-auto">
                        <pre className="whitespace-pre-wrap font-mono text-xs">
                          {formatIncEx(testCases[0].agent_test_case.evaluation_config.strict_fields)}
                        </pre>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <span className="font-medium text-sm">LLM Fields:</span>
                      <div className="mt-1 text-sm text-muted-foreground wrap-break-word bg-background p-2 rounded border max-h-32 overflow-y-auto">
                        <pre className="whitespace-pre-wrap font-mono text-xs">
                          {formatIncEx(testCases[0].agent_test_case.evaluation_config.llm_fields)}
                        </pre>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Prompt args */}
            <div>
              <h4 className="font-medium mb-3">Prompt args</h4>
              <div className="bg-muted/30 p-3 rounded-lg space-y-2">
                {Object.entries(testCases[0].agent_test_case.prompt_kwargs).map(([key, value]) => (
                  <div key={key} className="space-y-1">
                    <span className="font-medium text-sm">{key}:</span>
                    <div className="text-sm text-muted-foreground bg-background p-2 rounded border max-h-32 overflow-y-auto whitespace-pre-wrap">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Field-Level Analysis */}
            {/* {testCase.agent_test_case.evaluation_result?.field_comparisons &&
              testCase.agent_test_case.evaluation_result.field_comparisons.length > 0 && (
                <div>
                  <h4 className="font-medium mb-3">Field-Level Analysis</h4>
                  <div className="space-y-2">
                    {testCase.agent_test_case.evaluation_result.field_comparisons.map((comp, idx) => (
                      <FieldComparisonDetails key={idx} comparison={comp} />
                    ))}
                  </div>
                </div>
              )} */}

            {/* Expected vs Actual Output - Collapsible */}
            <div className="border-t pt-4">
              <h4 className="font-medium">Full Output Comparison</h4>

              <div className="space-y-4">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-left p-3 font-medium text-sm">Field</TableHead>
                      <TableHead className="text-left p-3 font-medium text-sm">Expected</TableHead>
                      {testCases.map((testCase, index) => (
                        <TableHead key={testCase.nodeid} className="text-left p-3 font-medium text-sm">
                          <p className="flex items-center gap-1">
                            <span>Actual #{index + 1}</span>
                            <span
                              className={cn(
                                'text-xs px-1 py-0.5 w-12 text-center rounded-md',
                                testCase.outcome === 'passed'
                                  ? 'text-green-600 bg-green-500/10'
                                  : 'text-red-600 bg-red-500/10',
                              )}
                            >
                              {testCase.outcome === 'passed' ? 'Passed' : 'Failed'}
                            </span>
                          </p>
                        </TableHead>
                      ))}
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
                              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                {String(expectedValue)}
                              </p>
                            ) : (
                              <span className="text-xs text-muted-foreground italic">Not specified</span>
                            )}
                          </TableCell>
                          {testCases.map((testCase) => {
                            const actualValue = getFlattenedObjectValue(
                              testCase.agent_test_case.actual_outputs[0],
                              key,
                            );

                            return (
                              <TableCell key={testCase.nodeid} className="wrap-anywhere align-top min-w-80">
                                {actualValue !== undefined ? (
                                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                    {String(actualValue)}
                                  </p>
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

            {/* Model Comparison Results */}
            {hasModelComparison && (
              <ModelComparisonSection
                modelComparisonResults={testCases[0].agent_test_case.model_comparison_results}
                selectedModel={selectedModel || undefined}
                onModelSelect={handleModelSelect}
              />
            )}

            {/* Evaluation Results */}
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
                      <Badge variant={evaluationResult?.passed ? 'success' : 'destructive'}>
                        {evaluationResult?.passed ? 'Passed' : 'Failed'}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1 bg-background p-2 rounded border max-h-64 overflow-y-auto whitespace-pre-wrap font-mono">
                      {evaluationResult?.rationale}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
