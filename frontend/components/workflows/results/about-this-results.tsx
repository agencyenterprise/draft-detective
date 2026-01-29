'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { EmptyState } from '@/components/shared/empty-state';
import { AboutThisState, ProjectDetailed, RequirementCheckResult, WorkflowRunType } from '@/lib/generated-api';
import { CheckCircle2, ChevronDown, FileQuestion, FileText, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface AboutThisResultsProps {
  project: ProjectDetailed;
  onNavigateToDocumentExplorer?: (chunkIndex?: number) => void;
}

// Centralized requirement configuration - mirrors backend REQUIREMENT_METADATA
const REQUIREMENT_CONFIG = [
  { field: 'context' as const, label: 'Establishes Context', level: 'sentence' },
  { field: 'objectives' as const, label: 'Explains Objectives', level: 'sentence' },
  { field: 'relationship' as const, label: 'Relationship to RAND Work', level: 'sentence' },
  { field: 'audience' as const, label: 'Intended Audience', level: 'sentence' },
  { field: 'source_tasp' as const, label: 'TASP Boilerplate', level: 'paragraph' },
  { field: 'source_funding' as const, label: 'Funding Statement', level: 'paragraph' },
];

function RequirementStatus({
  requirement,
  label,
  level,
}: {
  requirement: RequirementCheckResult | null | undefined;
  label: string;
  level: string;
}) {
  const [isOpen, setIsOpen] = useState(false);

  if (!requirement) {
    return (
      <div className="flex items-start gap-2 text-sm text-muted-foreground">
        <span className="text-muted-foreground mt-0.5">—</span>
        <div>
          <span className="font-medium">{label}</span>
          <span className="text-xs ml-2">(Not checked)</span>
        </div>
      </div>
    );
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          className={cn(
            'w-full flex items-start gap-2 text-sm p-2 rounded-md transition-colors hover:bg-muted/50',
            requirement.passed ? 'text-green-700' : 'text-red-700',
          )}
        >
          {requirement.passed ? (
            <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 text-left">
            <span className="font-medium">{label}</span>
            <Badge variant="outline" className="ml-2 text-xs">
              {level}
            </Badge>
          </div>
          <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 p-2 space-y-2">
          <p className={cn('text-xs', requirement.passed ? 'text-green-600/70' : 'text-muted-foreground')}>
            {requirement.explanation}
          </p>
          {requirement.matched_text && (
            <div className="p-2 rounded-md bg-muted/50 border text-xs">
              <p className="font-medium text-muted-foreground mb-1">Matched {level}:</p>
              <p className="text-foreground">{requirement.matched_text}</p>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function AboutThisResults({ project, onNavigateToDocumentExplorer }: AboutThisResultsProps) {
  const workflowDetails = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);

  // Get the about this workflow
  const aboutThisRun = workflowDetails.find((w) => w.run.type === WorkflowRunType.AboutThis);

  const state = useMemo(() => {
    return aboutThisRun?.state as AboutThisState | undefined;
  }, [aboutThisRun?.state]);

  // Stats
  const stats = useMemo(() => {
    if (!state) return { passed: 0, failed: 0, total: 6 };

    let passed = 0;
    let failed = 0;

    for (const { field } of REQUIREMENT_CONFIG) {
      const result = state[field];
      if (result) {
        if (result.passed) passed++;
        else failed++;
      }
    }

    return { passed, failed, total: 6 };
  }, [state]);

  if (!aboutThisRun) {
    return <EmptyState message="About This (Preface) analysis has not been run." />;
  }

  // No preface section found in the document
  if (!state?.found_section) {
    return (
      <EmptyState
        icon={FileQuestion}
        message="No Preface Section Found"
        description='The document doesn&apos;t appear to contain an "About This Report", "Preface", or similar introductory section. This analysis requires a preface section to validate.'
      >
        <div className="pt-2">
          <Badge variant="outline" className="text-xs">
            <FileText className="h-3 w-3 mr-1" />
            Section not found
          </Badge>
        </div>
      </EmptyState>
    );
  }

  const allPassed = stats.failed === 0 && stats.passed > 0;

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
                {allPassed ? 'All Preface Requirements Pass' : 'Preface Validation'}
              </CardTitle>
              <CardDescription>
                {allPassed
                  ? `Section "${state.section_title}" meets all 6 publication requirements`
                  : `Validates "${state.section_title}" against 6 publication requirements`}
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

      {/* Requirement checks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Requirement Checks</CardTitle>
          <CardDescription className="text-xs">Click each requirement to see details and matched text</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {REQUIREMENT_CONFIG.map(({ field, label, level }) => (
            <RequirementStatus key={field} requirement={state[field]} label={label} level={level} />
          ))}
        </CardContent>
      </Card>

      {/* Final summary if any failed */}
      {!allPassed && state.final_summary && (
        <Card className="border-amber-200">
          <CardHeader>
            <CardTitle className="text-sm text-amber-800">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-amber-700 whitespace-pre-wrap">{state.final_summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Section text preview */}
      <Card>
        <Collapsible>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm">Section Content</CardTitle>
                  <CardDescription className="text-xs">
                    View the extracted preface text ({state.section_text?.length ?? 0} characters)
                  </CardDescription>
                </div>
                <ChevronDown className="h-4 w-4" />
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              <div className="max-h-60 overflow-y-auto p-3 rounded-md bg-muted/50 border">
                <p className="text-sm text-foreground whitespace-pre-wrap">{state.section_text}</p>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>
    </div>
  );
}
