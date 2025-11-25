'use client';

import { Card, CardContent } from '@/components/ui/card';
import { useState } from 'react';
import { TestCase } from './types';
import { getFlattenedObjectKeys } from './util';
import { ModelComparisonSection } from './model-comparison-section';
import { TestCaseHeader } from './components/test-case-header';
import { TestConfigurationSection } from './components/test-configuration-section';
import { PromptArgsSection } from './components/prompt-args-section';
import { OutputComparisonTable } from './components/output-comparison-table';
import { EvaluationResultsSection } from './components/evaluation-results-section';
import { getDisplayResults } from './model-comparison-utils';

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

  if (!testCases[0]?.agent_test_case) {
    return (
      <div className="p-4 border rounded-lg">
        <p className="text-sm text-muted-foreground">No test case data available</p>
      </div>
    );
  }

  const hasModelComparison = testCases[0].agent_test_case.model_comparison_results;

  const expectedKeys = getFlattenedObjectKeys(testCases[0].agent_test_case.expected_output);
  const actualKeys = getFlattenedObjectKeys(testCases[0].agent_test_case.actual_outputs[0]);
  const allKeys = [...new Set([...expectedKeys, ...actualKeys])].sort((a, b) => a.localeCompare(b));

  return (
    <Card className="py-1">
      <TestCaseHeader
        name={name}
        testCases={testCases}
        accuracy={accuracy}
        isExpanded={isExpanded}
        onToggle={toggleExpanded}
      />

      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-6">
            <TestConfigurationSection testCase={testCases[0]} />

            {hasModelComparison && (
              <ModelComparisonSection
                modelComparisonResults={testCases[0].agent_test_case.model_comparison_results}
                selectedModel={selectedModel || undefined}
                onModelSelect={handleModelSelect}
              />
            )}

            <PromptArgsSection promptKwargs={testCases[0].agent_test_case.prompt_kwargs} />

            <OutputComparisonTable
              testCases={testCases}
              allKeys={allKeys}
              selectedModel={selectedModel}
              getDisplayResults={(tc) => getDisplayResults(tc, selectedModel)}
            />

            <EvaluationResultsSection
              testCases={testCases}
              selectedModel={selectedModel}
              getDisplayResults={(tc) => getDisplayResults(tc, selectedModel)}
            />
          </div>
        </CardContent>
      )}
    </Card>
  );
}
