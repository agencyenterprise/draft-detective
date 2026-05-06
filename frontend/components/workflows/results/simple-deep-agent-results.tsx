'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Markdown } from '@/components/markdown';
import { DocumentIssueCard } from '@/components/results/components/document-issue-card';
import { EmptyState } from '@/components/shared/empty-state';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Issue, ProjectDetailed, SeverityEnum, SimpleDeepAgentState } from '@/lib/generated-api';
import {
  isWorkflowCancelled,
  isWorkflowFailed,
  isWorkflowProcessing,
  WorkflowRunDetailTyped,
} from '@/lib/workflow-state';
import { AssistantRuntimeProvider, ThreadMessageLike, useExternalStoreRuntime } from '@assistant-ui/react';
import { convertLangChainMessages, LangChainMessage } from '@assistant-ui/react-langgraph';
import { Ban, CheckCircle2, ClipboardList, Loader2, MessageSquare, XCircle } from 'lucide-react';
import { useMemo } from 'react';

interface SimpleDeepAgentResultsProps {
  project: ProjectDetailed;
  workflowDetail: WorkflowRunDetailTyped<SimpleDeepAgentState>;
  workflowName: string;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}

function IssuesList({
  issues,
  onNavigateToDocumentExplorer,
}: {
  issues: Issue[];
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}) {
  const realIssues = issues.filter((i) => i.severity !== SeverityEnum.None);
  const informational = issues.filter((i) => i.severity === SeverityEnum.None);

  const handleSelect = (issue: Issue) => {
    if (typeof issue.start_line === 'number' && typeof issue.end_line === 'number') {
      onNavigateToDocumentExplorer([issue.start_line, issue.end_line]);
    } else {
      onNavigateToDocumentExplorer();
    }
  };

  return (
    <>
      {realIssues.length === 0 ? (
        <Card className="border-green-200 bg-green-50/30 dark:bg-green-950/30 dark:border-green-900">
          <CardContent className="flex items-center gap-3 py-6">
            <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-medium">All Checks Passed</p>
              <p className="text-xs text-muted-foreground">No issues were found in the document.</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            {realIssues.length} Issue{realIssues.length !== 1 ? 's' : ''} Found
          </h3>
          <div className="space-y-2">
            {realIssues.map((issue) => (
              <DocumentIssueCard key={issue.id} issue={issue} onSelect={handleSelect} />
            ))}
          </div>
        </section>
      )}

      {informational.length > 0 && (
        <section className="space-y-2 mt-4">
          <h3 className="text-sm font-medium text-muted-foreground">
            {informational.length} Informational Item{informational.length !== 1 ? 's' : ''}
          </h3>
          <div className="space-y-2">
            {informational.map((issue) => (
              <DocumentIssueCard key={issue.id} issue={issue} onSelect={handleSelect} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

export function SimpleDeepAgentResults({
  project,
  workflowDetail,
  workflowName,
  onNavigateToDocumentExplorer,
}: SimpleDeepAgentResultsProps) {
  const messages = workflowDetail.state?.messages ?? [];
  const displayedMessages = messages.filter((message) => message.type !== 'tool');

  const workflowRunId = workflowDetail.run.id;
  const issues = useMemo(
    () => (project.issues ?? []).filter((i) => i.workflow_run_id === workflowRunId),
    [project.issues, workflowRunId],
  );

  const runtime = useExternalStoreRuntime({
    messages: displayedMessages,
    convertMessage: (message) => convertLangChainMessages(message as LangChainMessage, {}) as ThreadMessageLike,
    isRunning: false,
    onNew: async () => {},
  });

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
    return <EmptyState message="No results available for this workflow run." />;
  }

  const { result } = state;

  return (
    <Tabs defaultValue="results">
      <TabsList>
        <TabsTrigger value="results" className="gap-1.5">
          <ClipboardList className="h-3.5 w-3.5" />
          Results
        </TabsTrigger>
        <TabsTrigger value="messages" className="gap-1.5">
          <MessageSquare className="h-3.5 w-3.5" />
          Messages
        </TabsTrigger>
      </TabsList>

      <TabsContent value="results" className="space-y-4">
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

        <IssuesList issues={issues} onNavigateToDocumentExplorer={onNavigateToDocumentExplorer} />
      </TabsContent>

      <TabsContent value="messages" className="mt-4">
        <AssistantRuntimeProvider runtime={runtime}>
          <ReadonlyThread />
        </AssistantRuntimeProvider>
      </TabsContent>
    </Tabs>
  );
}
