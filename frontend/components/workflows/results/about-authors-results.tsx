'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { CheckStatusItem } from '@/components/shared/check-status-item';
import { EmptyState } from '@/components/shared/empty-state';
import { NavigateToChunkButton } from '@/components/shared/navigate-to-chunk-button';
import { ValidationSummaryCard } from '@/components/shared/validation-summary-card';
import { AboutAuthorsState, AuthorValidationResult, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { CheckCircle2, ChevronDown, FileQuestion, Loader2, Users, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface AboutAuthorsResultsProps {
  project: ProjectDetailed;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

// Centralized rule configuration - mirrors backend RULE_METADATA
const RULE_CONFIG = [
  { field: 'rule_1_sentence_length' as const, label: 'Sentence Count (3 sentences)' },
  { field: 'rule_2_position_affiliation' as const, label: 'Position & Affiliation' },
  { field: 'rule_3_tasp_statement' as const, label: 'TASP Statement' },
  { field: 'rule_4_research_focus' as const, label: 'Research Focus' },
  { field: 'rule_5_highest_degree' as const, label: 'Highest Degree' },
] as const;

type RuleField = (typeof RULE_CONFIG)[number]['field'];

interface AuthorResultCardProps {
  result: AuthorValidationResult;
  onNavigateToChunk?: () => void;
}

function AuthorResultCard({ result, onNavigateToChunk }: AuthorResultCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  const failedRulesCount = useMemo(() => {
    return RULE_CONFIG.filter(({ field }) => {
      const rule = result[field as RuleField];
      return (rule.applicable ?? true) && !rule.passed;
    }).length;
  }, [result]);

  return (
    <Card className={cn(result.overall_passed ? 'border-green-200' : 'border-red-200')}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
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
              <ChevronDown className={cn('h-4 w-4 transition-transform flex-shrink-0 ml-2', isOpen && 'rotate-180')} />
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0 space-y-4">
            {/* Author bio text */}
            <div className="p-3 rounded-md bg-muted/50 border">
              <p className="text-sm text-foreground whitespace-pre-wrap">{result.author_text}</p>
              {onNavigateToChunk && <NavigateToChunkButton onClick={onNavigateToChunk} />}
            </div>

            {/* Rule checks using shared CheckStatusItem */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Rule Checks</h4>
              <div className="grid gap-2">
                {RULE_CONFIG.map(({ field, label }) => {
                  const rule = result[field as RuleField];
                  return (
                    <CheckStatusItem
                      key={field}
                      passed={rule.passed}
                      label={label}
                      explanation={rule.explanation}
                      applicable={rule.applicable ?? true}
                      expandable={false}
                    />
                  );
                })}
              </div>
            </div>

            {/* Guidance if failed */}
            {!result.overall_passed && result.guidance && (
              <div className="p-3 rounded-md bg-amber-50 border border-amber-200">
                <h4 className="text-xs font-semibold text-amber-800 mb-1">Suggested Improvements</h4>
                <p className="text-sm text-amber-700">{result.guidance}</p>
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

export function AboutAuthorsResults({ project, onNavigateToDocumentExplorer }: AboutAuthorsResultsProps) {
  const workflowRuns = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);
  const aboutAuthorsRun = getWorkflowRunByType(workflowRuns, WorkflowRunType.AboutAuthors);

  // Not run yet
  if (!aboutAuthorsRun) {
    return <EmptyState message="About Authors analysis has not been run." />;
  }

  // Still processing
  if (isWorkflowProcessing(aboutAuthorsRun)) {
    return (
      <EmptyState
        icon={Loader2}
        message="Analyzing Author Biographies..."
        description="The About Authors analysis is currently running. Results will appear here once complete."
      >
        <div className="pt-2">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </div>
      </EmptyState>
    );
  }

  return (
    <AboutAuthorsContent state={aboutAuthorsRun.state} onNavigateToDocumentExplorer={onNavigateToDocumentExplorer} />
  );
}

interface AboutAuthorsContentProps {
  state: AboutAuthorsState;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

function AboutAuthorsContent({ state, onNavigateToDocumentExplorer }: AboutAuthorsContentProps) {
  const results = useMemo(() => state.results ?? [], [state.results]);

  // Stats
  const stats = useMemo(() => {
    const passed = results.filter((r) => r.overall_passed).length;
    const failed = results.filter((r) => !r.overall_passed).length;
    return { passed, failed, total: results.length };
  }, [results]);

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

  return (
    <div className="space-y-6">
      {/* Summary */}
      <ValidationSummaryCard
        stats={stats}
        allPassedTitle="All Author Biographies Pass Validation"
        defaultTitle="About Authors Validation"
        allPassedDescription={`${stats.total} author${stats.total !== 1 ? 's' : ''} validated against publication rules`}
        defaultDescription={`Validates author biographies against ${RULE_CONFIG.length} publication rules: sentence count, position/affiliation, TASP statement, research focus, and highest degree.`}
      />

      {/* Results by author */}
      <div className="max-h-[50vh] overflow-y-auto space-y-3 pr-1">
        {results.map((result) => (
          <AuthorResultCard
            key={result.author_id}
            result={result}
            onNavigateToChunk={
              onNavigateToDocumentExplorer && result.chunk_indices?.length
                ? () => onNavigateToDocumentExplorer(result.chunk_indices!)
                : undefined
            }
          />
        ))}
      </div>
    </div>
  );
}
