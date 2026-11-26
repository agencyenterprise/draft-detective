'use client';

import { Markdown } from '@/components/shared/markdown';
import { AgentTranscript } from '@/components/workflows/results/agent-transcript';
import { WorkflowIssuesList } from '@/components/results/components/workflow-issues-list';
import { MarkdownDownloadButton } from '@/components/results/components/markdown-download-button';
import { EmptyState } from '@/components/shared/empty-state';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Issue, SimpleDeepAgentState } from '@/lib/generated-api';
import {
  isWorkflowCancelled,
  isWorkflowFailed,
  isWorkflowProcessing,
  WorkflowRunDetailTyped,
} from '@/lib/workflow-state';
import { Ban, ClipboardList, Loader2, MessageSquare, XCircle } from 'lucide-react';
import { useMemo } from 'react';

interface SimpleDeepAgentResultsProps {
  /** Every issue of the run's revision; the view picks the run's own. */
  issues: Issue[];
  canEditIssues: boolean;
  workflowDetail: WorkflowRunDetailTyped<SimpleDeepAgentState>;
  workflowName: string;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}

function ReportCard({ reportMarkdown }: { reportMarkdown: string }) {
  return (
    <Card className="gap-2">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm">Report</CardTitle>
        <MarkdownDownloadButton markdown={reportMarkdown} fileName="report" />
      </CardHeader>
      <CardContent className="text-sm">
        <Markdown>{reportMarkdown}</Markdown>
      </CardContent>
    </Card>
  );
}

export function SimpleDeepAgentResults({
  issues: allIssues,
  canEditIssues,
  workflowDetail,
  workflowName,
  onNavigateToDocumentExplorer,
}: SimpleDeepAgentResultsProps) {
  const workflowRunId = workflowDetail.run.id;
  const issues = useMemo(
    () => allIssues.filter((i) => i.workflow_run_id === workflowRunId),
    [allIssues, workflowRunId],
  );

  if (isWorkflowProcessing(workflowDetail)) {
    return (
      <EmptyState
        icon={<Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />}
        message={`Assessing Document…`}
        description={`The ${workflowName} assessment is currently running. Results will appear here once complete.`}
      />
    );
  }

  if (isWorkflowCancelled(workflowDetail)) {
    return (
      <EmptyState
        icon={<Ban className="h-8 w-8 text-muted-foreground mx-auto" />}
        message="Assessment Cancelled"
        description={`The ${workflowName} assessment was cancelled before it could complete.`}
      />
    );
  }

  if (isWorkflowFailed(workflowDetail)) {
    return (
      <EmptyState
        icon={<XCircle className="h-8 w-8 text-red-600 mx-auto" />}
        message="Assessment Failed"
        description={
          workflowDetail.run.failure_message ??
          `The ${workflowName} assessment failed before it could complete. Please retry it.`
        }
      />
    );
  }

  const state = workflowDetail.state as SimpleDeepAgentState | undefined;

  if (!state?.result) {
    return <EmptyState message="No results available for this run." />;
  }

  const { result } = state;

  return (
    <Tabs defaultValue="results">
      <div className="flex items-center justify-between gap-2">
        <TabsList>
          {/* The tooltip hangs off a wrapper, not the trigger itself: Radix
              writes data-state="closed" on whatever it is attached to, which
              would overwrite the data-state="active" the tab styles itself by. */}
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex h-full flex-1">
                <TabsTrigger value="results" className="gap-1.5">
                  <ClipboardList className="h-3.5 w-3.5" />
                  Results
                </TabsTrigger>
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              What this assessment concluded: its report and the issues it raised.
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex h-full flex-1">
                <TabsTrigger value="messages" className="gap-1.5">
                  <MessageSquare className="h-3.5 w-3.5" />
                  Messages
                </TabsTrigger>
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              The agent&apos;s own transcript: what it read and how it worked its way to those results.
            </TooltipContent>
          </Tooltip>
        </TabsList>
      </div>

      <TabsContent value="results" className="space-y-4">
        {result.report_markdown && <ReportCard reportMarkdown={result.report_markdown} />}
        <WorkflowIssuesList
          issues={issues}
          readOnly={!canEditIssues}
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      </TabsContent>

      <TabsContent value="messages">
        <AgentTranscript messages={state.messages ?? []} />
      </TabsContent>
    </Tabs>
  );
}
