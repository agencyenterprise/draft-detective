'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Markdown } from '@/components/markdown';
import { EmptyState } from '@/components/shared/empty-state';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgentCheckResult, SimpleDeepAgentState } from '@/lib/generated-api';
import { isWorkflowCancelled, isWorkflowProcessing, WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { AssistantRuntimeProvider, ThreadMessageLike, useExternalStoreRuntime } from '@assistant-ui/react';
import { convertLangChainMessages, LangChainMessage } from '@assistant-ui/react-langgraph';
import { AlertTriangle, Ban, CheckCircle2, ClipboardList, Loader2, MessageSquare } from 'lucide-react';

interface SimpleDeepAgentResultsProps {
  workflowDetail: WorkflowRunDetailTyped<SimpleDeepAgentState>;
  workflowName: string;
}

function IssuesList({ result }: { result: AgentCheckResult }) {
  const issues = result.issues ?? [];

  if (issues.length === 0) {
    return (
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
    );
  }

  return (
    <Card className="border-amber-200 gap-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-amber-800">
          {issues.length} Issue{issues.length !== 1 ? 's' : ''} Found
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {issues.map((issue, idx) => (
          <div
            key={idx}
            className="flex items-start gap-2 p-2 rounded-md bg-amber-50 dark:bg-amber-950 border border-amber-100 dark:bg-amber-950/40 dark:border-amber-900"
          >
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">{issue.title}</p>
              <p className="text-xs text-amber-700 mt-0.5">{issue.description}</p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function SimpleDeepAgentResults({ workflowDetail, workflowName }: SimpleDeepAgentResultsProps) {
  const messages = workflowDetail.state?.messages ?? [];
  const displayedMessages = messages.filter((message) => message.type !== 'tool');

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
        <IssuesList result={result} />

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
      </TabsContent>

      <TabsContent value="messages" className="mt-4">
        <AssistantRuntimeProvider runtime={runtime}>
          <ReadonlyThread />
        </AssistantRuntimeProvider>
      </TabsContent>
    </Tabs>
  );
}
