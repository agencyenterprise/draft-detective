'use client';

import { Markdown } from '@/components/markdown';
import { EmptyState } from '@/components/shared/empty-state';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AboutThisGerState, AgentCheckResult, WorkflowRunDetail } from '@/lib/generated-api';
import { isWorkflowCancelled, isWorkflowProcessing } from '@/lib/workflow-state';
import { AlertTriangle, Ban, BookOpen, CheckCircle2, FileQuestion, Loader2, Users } from 'lucide-react';
import { useState } from 'react';

interface AboutThisGerResultsProps {
  workflowDetail: WorkflowRunDetail;
}

function SectionResult({
  result,
  sectionLabel,
}: {
  result: AgentCheckResult | null | undefined;
  sectionLabel: string;
}) {
  if (!result) {
    return (
      <EmptyState
        icon={FileQuestion}
        message={`No ${sectionLabel} results`}
        description={`The ${sectionLabel.toLowerCase()} check did not produce results.`}
      />
    );
  }

  const issues = result.issues ?? [];

  return (
    <div className="space-y-4">
      {issues.length > 0 && (
        <Card className="border-amber-200 gap-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-amber-800 dark:text-amber-200">
              {issues.length} Issue{issues.length !== 1 ? 's' : ''} Found
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {issues.map((issue, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 p-2 rounded-md bg-amber-50 border border-amber-100 dark:bg-amber-950/40 dark:border-amber-900"
              >
                <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{issue.title}</p>
                  <p className="text-xs text-amber-700 dark:text-amber-300 mt-0.5">{issue.description}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {issues.length === 0 && (
        <Card className="border-green-200 bg-green-50/30 dark:bg-green-950/30 dark:border-green-900">
          <CardContent className="flex items-center gap-3 py-6">
            <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-medium">All {sectionLabel} Checks Passed</p>
              <p className="text-xs text-muted-foreground">
                No issues found in the {sectionLabel.toLowerCase()} section.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {result.report_markdown && (
        <Card className="gap-2">
          <CardHeader>
            <CardTitle className="text-sm">Report</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <Markdown>{result.report_markdown}</Markdown>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AboutThisGerContent({ state }: { state: AboutThisGerState }) {
  const [activeTab, setActiveTab] = useState('preface');

  const prefaceIssueCount = state.preface_result?.issues?.length ?? 0;
  const authorsIssueCount = state.authors_result?.issues?.length ?? 0;

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="preface" className="gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            Preface
            {prefaceIssueCount > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 px-1.5 text-xs">
                {prefaceIssueCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="authors" className="gap-1.5">
            <Users className="h-3.5 w-3.5" />
            Authors
            {authorsIssueCount > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 px-1.5 text-xs">
                {authorsIssueCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preface" className="mt-4">
          <SectionResult result={state.preface_result} sectionLabel="Preface" />
        </TabsContent>

        <TabsContent value="authors" className="mt-4">
          <SectionResult result={state.authors_result} sectionLabel="Authors" />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export function AboutThisGerResults({ workflowDetail }: AboutThisGerResultsProps) {
  if (isWorkflowProcessing(workflowDetail)) {
    return (
      <EmptyState
        icon={<Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />}
        message="Assessing Document..."
        description="The About This (GER) assessment is currently running. Results will appear here once complete."
      />
    );
  }

  if (isWorkflowCancelled(workflowDetail)) {
    return (
      <EmptyState
        icon={<Ban className="h-8 w-8 text-muted-foreground mx-auto" />}
        message="Assessment Cancelled"
        description="The About This (GER) assessment was cancelled before it could complete."
      />
    );
  }

  const state = workflowDetail.state as AboutThisGerState | undefined;

  if (!state) {
    return <EmptyState message="No results available for this workflow run." />;
  }

  return <AboutThisGerContent state={state} />;
}
