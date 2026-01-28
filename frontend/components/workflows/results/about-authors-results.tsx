'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, ExpandableCard, NavigateToChunkButton } from '@/components/shared';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { CheckCircle2, FileQuestion, Users, XCircle } from 'lucide-react';
import * as React from 'react';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface AboutAuthorsResultsProps {
  project: ProjectDetailed;
  onNavigateToDocumentExplorer?: (chunkIndex?: number) => void;
}

interface RuleCheckResult {
  passed: boolean;
  explanation: string;
  applicable: boolean;
}

interface AuthorValidationResult {
  author_id: string;
  author_text: string;
  author_name: string;
  author_name_positions: number[];
  chunk_indices: number[];
  rule_1_sentence_length: RuleCheckResult;
  rule_2_position_affiliation: RuleCheckResult;
  rule_3_tasp_statement: RuleCheckResult;
  rule_4_research_focus: RuleCheckResult;
  rule_5_highest_degree: RuleCheckResult;
  overall_passed: boolean;
  final_comment: string;
  guidance?: string | null;
}

interface AboutAuthorsState {
  type: string;
  results: AuthorValidationResult[];
  errors?: unknown[];
}

// Centralized rule configuration - mirrors backend RULE_METADATA
const RULE_CONFIG = [
  { field: 'rule_1_sentence_length' as const, key: 'rule_1', label: 'Sentence Count (3 sentences)' },
  { field: 'rule_2_position_affiliation' as const, key: 'rule_2', label: 'Position & Affiliation' },
  { field: 'rule_3_tasp_statement' as const, key: 'rule_3', label: 'TASP Statement' },
  { field: 'rule_4_research_focus' as const, key: 'rule_4', label: 'Research Focus' },
  { field: 'rule_5_highest_degree' as const, key: 'rule_5', label: 'Highest Degree' },
];

function RuleStatus({ rule, label }: { rule: RuleCheckResult; label: string }) {
  if (!rule.applicable) {
    return (
      <div className="flex items-start gap-2 text-sm text-muted-foreground">
        <span className="text-muted-foreground mt-0.5">—</span>
        <div>
          <span className="font-medium">{label}</span>
          <span className="text-xs ml-2">(N/A)</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex items-start gap-2 text-sm', rule.passed ? 'text-green-700' : 'text-red-700')}>
      {rule.passed ? (
        <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
      ) : (
        <XCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
      )}
      <div>
        <span className="font-medium">{label}</span>
        {rule.explanation && (
          <p className={cn('text-xs mt-0.5', rule.passed ? 'text-green-600/70' : 'text-muted-foreground')}>
            {rule.explanation}
          </p>
        )}
      </div>
    </div>
  );
}

interface AuthorResultCardProps {
  result: AuthorValidationResult;
  onNavigateToChunk?: () => void;
}

function AuthorResultCard({ result, onNavigateToChunk }: AuthorResultCardProps) {
  const failedRulesCount = useMemo(() => {
    return RULE_CONFIG.filter(({ field }) => {
      const rule = result[field];
      return rule.applicable && !rule.passed;
    }).length;
  }, [result]);

  const header = (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          'h-8 w-8 rounded-full flex items-center justify-center',
          result.overall_passed ? 'bg-green-100' : 'bg-red-100',
        )}
      >
        {result.overall_passed ? (
          <CheckCircle2 className="h-4 w-4 text-green-600" />
        ) : (
          <XCircle className="h-4 w-4 text-red-600" />
        )}
      </div>
      <div>
        <CardTitle className="text-sm font-medium">{result.author_name}</CardTitle>
        <CardDescription className="text-xs">
          {result.overall_passed ? (
            'All rules passed'
          ) : (
            <span className="text-red-600">
              {failedRulesCount} rule{failedRulesCount !== 1 ? 's' : ''} failed
            </span>
          )}
        </CardDescription>
      </div>
    </div>
  );

  return (
    <ExpandableCard
      header={header}
      className={cn(result.overall_passed ? 'border-green-200' : 'border-red-200')}
      contentClassName="space-y-4"
    >
      {/* Author bio text */}
      <div className="p-3 rounded-md bg-muted/50 border">
        <p className="text-sm text-foreground whitespace-pre-wrap">{result.author_text}</p>
        {onNavigateToChunk && <NavigateToChunkButton onClick={onNavigateToChunk} />}
      </div>

      {/* Rule checks */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Rule Checks</h4>
        <div className="grid gap-2">
          {RULE_CONFIG.map(({ field, label }) => (
            <RuleStatus key={field} rule={result[field]} label={label} />
          ))}
        </div>
      </div>

      {/* Guidance if failed */}
      {!result.overall_passed && result.guidance && (
        <div className="p-3 rounded-md bg-amber-50 border border-amber-200">
          <h4 className="text-xs font-semibold text-amber-800 mb-1">Suggested Improvements</h4>
          <p className="text-sm text-amber-700">{result.guidance}</p>
        </div>
      )}
    </ExpandableCard>
  );
}

export function AboutAuthorsResults({ project, onNavigateToDocumentExplorer }: AboutAuthorsResultsProps) {
  const workflowDetails = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);

  // Get the about authors workflow
  const aboutAuthorsRun = workflowDetails.find((w) => w.run.type === ('about_authors' as WorkflowRunType));

  const results = useMemo(() => {
    const state = aboutAuthorsRun?.state as AboutAuthorsState | undefined;
    return state?.results ?? [];
  }, [aboutAuthorsRun?.state]);

  // Stats
  const stats = useMemo(() => {
    const passed = results.filter((r) => r.overall_passed).length;
    const failed = results.filter((r) => !r.overall_passed).length;
    return { passed, failed, total: results.length };
  }, [results]);

  if (!aboutAuthorsRun) {
    return <EmptyState message="About Authors analysis has not been run." />;
  }

  // No "About the Authors" section found in the document
  if (results.length === 0) {
    return (
      <EmptyState
        icon={FileQuestion}
        message='No "About the Authors" Section Found'
        description='The document doesn&apos;t appear to contain an "About the Authors" or "Author Biographies" section. This analysis requires author biography paragraphs to validate.'
      >
        <div className="pt-2">
          <Badge variant="outline" className="text-xs">
            <Users className="h-3 w-3 mr-1" />0 authors detected
          </Badge>
        </div>
      </EmptyState>
    );
  }

  const allPassed = stats.failed === 0;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <Card className={allPassed ? 'border-green-200 bg-green-50/30' : undefined}>
        <CardHeader>
          <div className="flex items-center gap-3">
            {allPassed && (
              <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
            )}
            <div>
              <CardTitle className="text-base">
                {allPassed ? 'All Author Biographies Pass Validation' : 'About Authors Validation'}
              </CardTitle>
              <CardDescription>
                {allPassed
                  ? `${stats.total} author${stats.total !== 1 ? 's' : ''} validated against publication rules`
                  : 'Validates author biographies against 5 publication rules: sentence count, position/affiliation, TASP statement, research focus, and highest degree.'}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        {!allPassed && (
          <CardContent>
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-green-50">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-700">{stats.passed} Passed</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-red-50">
                <XCircle className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-700">{stats.failed} Failed</span>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Results by author */}
      <div className="max-h-[50vh] overflow-y-auto space-y-3 pr-1">
        {results.map((result) => (
          <AuthorResultCard
            key={result.author_id}
            result={result}
            onNavigateToChunk={
              onNavigateToDocumentExplorer && result.chunk_indices.length > 0
                ? () => onNavigateToDocumentExplorer(result.chunk_indices[0])
                : undefined
            }
          />
        ))}
      </div>
    </div>
  );
}
