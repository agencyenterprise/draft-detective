'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, BotIcon, ChevronDown, ChevronRight, Clock } from 'lucide-react';
import { useState } from 'react';
import { percentageFormatter } from './formatters';
import { GroupedTestCaseItem } from './grouped-test-case-item';
import { TestCase } from './types';
import { aggregateFieldInsights, calculateConsistency, formatDuration } from './util';
import { ModelComparisonSummary } from './model-comparison-summary';

interface AgentSummary {
  agentName: string;
  testCases: TestCase[];
  total: number;
  passed: number;
  failed: number;
  accuracy: number;
  totalDuration: number;
  averageDuration: number;
  consistencyProbabilityAvg: number;
  consistencyProbabilityByTestCase: Record<string, number>;
}

interface AgentSummaryCardProps {
  summary: AgentSummary;
  showOnlyFailed?: boolean;
}

export function AgentSummaryCard({ summary, showOnlyFailed = false }: AgentSummaryCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showFieldInsights, setShowFieldInsights] = useState(true);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Calculate field insights
  const fieldInsights = aggregateFieldInsights(summary.testCases);
  const problematicFields = fieldInsights.filter((f) => f.accuracy < 100).slice(0, 5);

  const groupedTestCases = groupTestCasesByName(summary.testCases);
  const sortedGroupedTestCases = Array.from(groupedTestCases.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="cursor-pointer" onClick={toggleExpanded}>
          <div className="flex items-center gap-2 justify-between">
            <div className="flex items-center gap-2">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <div className="flex items-center gap-2">
                <BotIcon className="h-4 w-4" />
                <CardTitle>{summary.agentName}</CardTitle>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant={summary.accuracy >= 80 ? 'success' : summary.accuracy >= 60 ? 'secondary' : 'destructive'}
              >
                {summary.accuracy}% Accuracy
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Summary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-4">
          <div className="text-center p-3 bg-muted/30 rounded-lg">
            <div className="text-lg font-bold text-foreground">{summary.total}</div>
            <div className="text-xs text-muted-foreground">Total Tests</div>
          </div>
          <div className="text-center p-3 bg-green-50 rounded-lg">
            <div className="text-lg font-bold text-green-600">{summary.passed}</div>
            <div className="text-xs text-muted-foreground">Passed</div>
          </div>
          <div className="text-center p-3 bg-red-50 rounded-lg">
            <div className="text-lg font-bold text-red-600">{summary.failed}</div>
            <div className="text-xs text-muted-foreground">Failed</div>
          </div>
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-lg font-bold text-blue-600">{summary.accuracy}%</div>
            <div className="text-xs text-muted-foreground">Accuracy</div>
          </div>
          <div className="text-center p-3 bg-amber-50 rounded-lg">
            <div className="text-lg font-bold text-amber-600">
              {percentageFormatter.format(summary.consistencyProbabilityAvg)}
            </div>
            <div className="text-xs text-muted-foreground">Consistency Probability</div>
          </div>
          <div className="text-center p-3 bg-purple-50 rounded-lg">
            <div className="text-lg font-bold text-purple-600 flex items-center justify-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDuration(summary.averageDuration)}
            </div>
            <div className="text-xs text-muted-foreground">Avg Duration</div>
          </div>
        </div>

        {/* Model Comparison Summary */}
        {isExpanded && <ModelComparisonSummary testCases={summary.testCases} />}

        {/* Field Performance Insights */}
        {isExpanded && problematicFields.length > 0 && (
          <div className="pb-4 pt-4 border-b">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-orange-500" />
                <h4 className="font-medium text-sm">Field Performance Issues</h4>
              </div>
              <button
                onClick={() => setShowFieldInsights(!showFieldInsights)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {showFieldInsights ? 'Hide' : 'Show'}
              </button>
            </div>
            {showFieldInsights && (
              <div className="space-y-1.5">
                {fieldInsights.map((insight) => (
                  <div
                    key={insight.field}
                    className="flex items-center justify-between p-2 bg-muted/30 rounded text-xs"
                  >
                    <code className="font-mono">{insight.field}</code>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">
                        {insight.passed}/{insight.total}
                      </span>
                      <Badge
                        variant={
                          insight.accuracy >= 80 ? 'success' : insight.accuracy >= 60 ? 'secondary' : 'destructive'
                        }
                        className="text-xs"
                      >
                        {insight.accuracy}%
                      </Badge>
                    </div>
                  </div>
                ))}
                {fieldInsights.length > 5 && (
                  <p className="text-xs text-muted-foreground text-center pt-1">
                    ... and {fieldInsights.length - 5} more field(s)
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Test Cases */}
        {isExpanded && (
          <div className="space-y-2 border-t pt-4">
            <h4 className="font-medium text-sm text-muted-foreground">Test Cases</h4>

            {sortedGroupedTestCases
              .filter(([, testCases]) => !showOnlyFailed || testCases.some((testCase) => testCase.outcome === 'failed'))
              .map(([name, testCases], index) => (
                <GroupedTestCaseItem key={index} name={name} testCases={testCases} consistencyProbability={0} />
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function groupTestCasesByName(testCases: TestCase[]): Map<string, TestCase[]> {
  const groupedTestCases = new Map<string, TestCase[]>();
  testCases.forEach((testCase) => {
    const name = testCase.agent_test_case.name;
    if (!groupedTestCases.has(name)) {
      groupedTestCases.set(name, []);
    }
    groupedTestCases.get(name)!.push(testCase);
  });
  return groupedTestCases;
}

// Utility function to group test cases by agent name
export function groupTestCasesByAgent(testCases: TestCase[]): AgentSummary[] {
  const agentGroups = new Map<string, TestCase[]>();

  // Group test cases by agent name
  testCases.forEach((testCase) => {
    // Skip test cases that don't have the expected agent structure
    if (!testCase.agent_test_case?.agent?.name) {
      return;
    }

    const agentName = testCase.agent_test_case.agent.name;
    if (!agentGroups.has(agentName)) {
      agentGroups.set(agentName, []);
    }
    agentGroups.get(agentName)!.push(testCase);
  });

  // Calculate summary statistics for each agent group
  return Array.from(agentGroups.entries())
    .map(([agentName, cases]) => {
      const total = cases.length;
      const passed = cases.filter((c) => c.outcome === 'passed').length;
      const failed = cases.filter((c) => c.outcome === 'failed').length;
      const accuracy = total > 0 ? Math.round((passed / total) * 100) : 0;
      const totalDuration = cases.reduce((sum, c) => sum + c.call.duration, 0);
      const averageDuration = total > 0 ? totalDuration / total : 0;
      const { avg: consistencyProbabilityAvg, byTestCase: consistencyProbabilityByTestCase } =
        calculateConsistency(cases);

      return {
        agentName,
        testCases: cases.sort((a, b) => a.nodeid.localeCompare(b.nodeid)),
        total,
        passed,
        failed,
        accuracy,
        totalDuration,
        averageDuration,
        consistencyProbabilityAvg,
        consistencyProbabilityByTestCase,
      };
    })
    .sort((a, b) => b.accuracy - a.accuracy); // Sort by accuracy descending
}
