'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Markdown } from '@/components/markdown';
import { HtmlReportFrame, HtmlReportFrameHandle } from '@/components/results/components/html-report-frame';
import { WorkflowIssuesList } from '@/components/results/components/workflow-issues-list';
import { MarkdownDownloadButton } from '@/components/results/components/markdown-download-button';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/shared/empty-state';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { AccessLevel, ProjectDetailed, SimpleDeepAgentState } from '@/lib/generated-api';
import {
  isWorkflowCancelled,
  isWorkflowFailed,
  isWorkflowProcessing,
  WorkflowRunDetailTyped,
} from '@/lib/workflow-state';
import { AssistantRuntimeProvider, ThreadMessageLike, useExternalStoreRuntime } from '@assistant-ui/react';
import { convertLangChainMessages, LangChainMessage } from '@assistant-ui/react-langgraph';
import { Ban, ClipboardList, Download, Loader2, MessageSquare, XCircle } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';

interface SimpleDeepAgentResultsProps {
  project: ProjectDetailed;
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

  // Declared above the early returns below, so the hook order stays stable.
  // The tab is controlled because the Download PDF button sits in the tab row
  // and only applies to the Results tab.
  const [activeTab, setActiveTab] = useState('results');
  const frameRef = useRef<HtmlReportFrameHandle>(null);

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
    <Tabs value={activeTab} onValueChange={setActiveTab}>
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
        {/* Only on the Results tab: the other tab unmounts the frame, which
            would leave this printing nothing. */}
        {result.report_html && activeTab === 'results' && (
          <Button variant="outline" size="sm" onClick={() => frameRef.current?.print()}>
            <Download className="size-4" />
            Download PDF
          </Button>
        )}
      </div>

      <TabsContent value="results" className="space-y-4">
        {result.report_html ? (
          // HTML-report workflows produce a document deliverable, not a checklist.
          // No Card wrapper: the report renders in its own bordered frame already.
          <HtmlReportFrame ref={frameRef} html={result.report_html} title="Report" />
        ) : (
          <>
            {result.report_markdown && <ReportCard reportMarkdown={result.report_markdown} />}
            <WorkflowIssuesList
              issues={issues}
              readOnly={project.access_level !== AccessLevel.Write}
              onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
            />
          </>
        )}
      </TabsContent>

      {/* No top margin: the Tabs root already spaces panels from the tab list,
          and the thread's own viewport padding is dropped for the same reason. */}
      <TabsContent value="messages">
        <AssistantRuntimeProvider runtime={runtime}>
          <ReadonlyThread viewportClassName="pt-0" />
        </AssistantRuntimeProvider>
      </TabsContent>
    </Tabs>
  );
}
