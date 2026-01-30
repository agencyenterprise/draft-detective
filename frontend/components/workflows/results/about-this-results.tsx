'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { CheckStatusItem } from '@/components/shared/check-status-item';
import { EmptyState } from '@/components/shared/empty-state';
import { ValidationSummaryCard } from '@/components/shared/validation-summary-card';
import { AboutThisState, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { ChevronDown, FileQuestion, FileText, Loader2 } from 'lucide-react';
import { useMemo } from 'react';

interface AboutThisResultsProps {
  project: ProjectDetailed;
}

// Centralized requirement configuration - mirrors backend REQUIREMENT_METADATA
const REQUIREMENT_CONFIG = [
  { field: 'context' as const, label: 'Establishes Context', level: 'sentence' },
  { field: 'objectives' as const, label: 'Explains Objectives', level: 'sentence' },
  { field: 'relationship' as const, label: 'Relationship to RAND Work', level: 'sentence' },
  { field: 'audience' as const, label: 'Intended Audience', level: 'sentence' },
  { field: 'source_tasp' as const, label: 'TASP Boilerplate', level: 'paragraph' },
  { field: 'source_funding' as const, label: 'Funding Statement', level: 'paragraph' },
] as const;

type RequirementField = (typeof REQUIREMENT_CONFIG)[number]['field'];

/**
 * Calculate validation statistics from the workflow state.
 */
function calculateStats(state: AboutThisState | undefined) {
  if (!state) return { passed: 0, failed: 0, total: REQUIREMENT_CONFIG.length };

  let passed = 0;
  let failed = 0;

  for (const { field } of REQUIREMENT_CONFIG) {
    const result = state[field as RequirementField];
    if (result) {
      if (result.passed) passed++;
      else failed++;
    }
  }

  return { passed, failed, total: REQUIREMENT_CONFIG.length };
}

export function AboutThisResults({ project }: AboutThisResultsProps) {
  const workflowRuns = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);
  const aboutThisRun = getWorkflowRunByType(workflowRuns, WorkflowRunType.AboutThis);

  // Not run yet
  if (!aboutThisRun) {
    return <EmptyState message="About This (Preface) analysis has not been run." />;
  }

  // Still processing
  if (isWorkflowProcessing(aboutThisRun)) {
    return (
      <EmptyState
        icon={Loader2}
        message="Analyzing Preface Section..."
        description="The About This (Preface) analysis is currently running. Results will appear here once complete."
      >
        <div className="pt-2">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </div>
      </EmptyState>
    );
  }

  return <AboutThisContent state={aboutThisRun.state} />;
}

interface AboutThisContentProps {
  state: AboutThisState;
}

function AboutThisContent({ state }: AboutThisContentProps) {
  const stats = useMemo(() => calculateStats(state), [state]);

  // No preface section found in the document
  if (!state.found_section) {
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
      <ValidationSummaryCard
        stats={stats}
        allPassedTitle="All Preface Requirements Pass"
        defaultTitle="Preface Validation"
        allPassedDescription={`Section "${state.section_title}" meets all ${REQUIREMENT_CONFIG.length} publication requirements`}
        defaultDescription={`Validates "${state.section_title}" against ${REQUIREMENT_CONFIG.length} publication requirements`}
      />

      {/* Requirement checks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Requirement Checks</CardTitle>
          <CardDescription className="text-xs">Click each requirement to see details and matched text</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {REQUIREMENT_CONFIG.map(({ field, label, level }) => {
            const requirement = state[field as RequirementField];
            return (
              <CheckStatusItem
                key={field}
                passed={requirement?.passed ?? false}
                label={label}
                level={level}
                explanation={requirement?.explanation}
                matchedText={requirement?.matched_text}
                applicable={!!requirement}
                expandable={true}
              />
            );
          })}
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

      {/* Section text preview - inlined since only used here */}
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
