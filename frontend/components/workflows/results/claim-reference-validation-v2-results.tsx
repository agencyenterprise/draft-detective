'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Markdown } from '@/components/markdown';
import { EmptyState } from '@/components/shared/empty-state';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ClaimReferenceValidationV2Response,
  ClaimReferenceValidationV2State,
  EvidenceAlignmentLevel,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { AssistantRuntimeProvider, ThreadMessageLike, useExternalStoreRuntime } from '@assistant-ui/react';
import { convertLangChainMessages, LangChainMessage } from '@assistant-ui/react-langgraph';
import { CheckCircle2, CircleHelp, ListChecks, MessageSquare, ShieldAlert, ShieldCheck } from 'lucide-react';

import { ClaimResultItem } from './claim-reference-validation-v2-result-item';

interface ClaimReferenceValidationV2ResultsProps {
  workflowDetail: WorkflowRunDetail;
}

type Message = NonNullable<ClaimReferenceValidationV2State['messages']>[number];

/**
 * Convert LangChain message format to assistant-ui ThreadMessageLike format
 */
function convertMessage(message: Message): ThreadMessageLike {
  const convertedMessage = convertLangChainMessages(message as LangChainMessage, {});
  return convertedMessage as ThreadMessageLike;
}

export function ClaimReferenceValidationV2Results({ workflowDetail }: ClaimReferenceValidationV2ResultsProps) {
  const state = workflowDetail.state as ClaimReferenceValidationV2State;

  if (!state) {
    return <EmptyState message="No results available for this workflow run." />;
  }

  const messages = state?.messages ?? [];
  const displayedMessages = messages.filter((message) => message.type !== 'tool');
  const response = state.response;

  return (
    <Tabs defaultValue={response ? 'results' : 'messages'}>
      <TabsList>
        <TabsTrigger value="results">
          <ListChecks className="h-4 w-4 mr-1.5" />
          Results
          {response && (
            <Badge className="ml-1.5 rounded-full h-4.5 min-w-4.5" variant="secondary">
              {response.results.length}
            </Badge>
          )}
        </TabsTrigger>
        <TabsTrigger value="messages">
          <MessageSquare className="h-4 w-4 mr-1.5" />
          Messages
        </TabsTrigger>
      </TabsList>

      <TabsContent value="results">
        <ResultsTab response={response} />
      </TabsContent>

      <TabsContent value="messages">
        <MessagesTab messages={displayedMessages} convertMessage={convertMessage} />
      </TabsContent>
    </Tabs>
  );
}

function MessagesTab({
  messages,
  convertMessage,
}: {
  messages: Message[];
  convertMessage: (message: Message) => ThreadMessageLike;
}) {
  const runtime = useExternalStoreRuntime({
    messages,
    convertMessage,
    isRunning: false,
    onNew: async () => {},
  });

  if (messages.length === 0) {
    return (
      <EmptyState
        icon={MessageSquare}
        message="No Messages Yet"
        description="The claim reference validation analysis has not produced any messages yet. This may indicate the workflow is still initializing or waiting for input."
      />
    );
  }

  return (
    <div className="h-[600px] text-sm">
      <AssistantRuntimeProvider runtime={runtime}>
        <ReadonlyThread />
      </AssistantRuntimeProvider>
    </div>
  );
}

function ResultsTab({ response }: { response?: ClaimReferenceValidationV2Response | null }) {
  if (!response) {
    return (
      <EmptyState
        icon={ListChecks}
        message="No Results Yet"
        description="The claim reference validation has not produced structured results yet. Check the Messages tab for progress."
      />
    );
  }

  const results = response.results;
  const alignmentCounts = results.reduce(
    (acc, r) => {
      acc[r.evidence_alignment] = (acc[r.evidence_alignment] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="space-y-4 pt-2">
      {/* Summary bar */}
      <div className="flex flex-wrap items-center gap-3 p-3 bg-muted/50 rounded-lg">
        <span className="text-sm font-medium">
          {results.length} {results.length === 1 ? 'claim' : 'claims'} analyzed
        </span>
        <div className="flex gap-2">
          {(alignmentCounts[EvidenceAlignmentLevel.Supported] ?? 0) > 0 && (
            <Badge variant="outline" className="border-green-300 bg-green-50 text-green-700">
              <ShieldCheck className="mr-1 h-3 w-3" />
              {alignmentCounts[EvidenceAlignmentLevel.Supported]} Supported
            </Badge>
          )}
          {(alignmentCounts[EvidenceAlignmentLevel.PartiallySupported] ?? 0) > 0 && (
            <Badge variant="outline" className="border-yellow-300 bg-yellow-50 text-yellow-700">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              {alignmentCounts[EvidenceAlignmentLevel.PartiallySupported]} Partial
            </Badge>
          )}
          {(alignmentCounts[EvidenceAlignmentLevel.Unsupported] ?? 0) > 0 && (
            <Badge variant="outline" className="border-red-300 bg-red-50 text-red-700">
              <ShieldAlert className="mr-1 h-3 w-3" />
              {alignmentCounts[EvidenceAlignmentLevel.Unsupported]} Unsupported
            </Badge>
          )}
          {(alignmentCounts[EvidenceAlignmentLevel.Unverifiable] ?? 0) > 0 && (
            <Badge variant="outline" className="border-gray-300 bg-gray-50 text-gray-700">
              <CircleHelp className="mr-1 h-3 w-3" />
              {alignmentCounts[EvidenceAlignmentLevel.Unverifiable]} Unverifiable
            </Badge>
          )}
        </div>
      </div>

      {/* Reasoning section */}
      {response.reasoning && (
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-semibold mb-2">Reasoning</h4>
          <div className="text-sm prose prose-sm max-w-none">
            <Markdown>{response.reasoning}</Markdown>
          </div>
        </div>
      )}

      {/* Results list */}
      <div className="space-y-3">
        {results.map((item, index) => (
          <ClaimResultItem key={`${item.line_start}-${item.line_end}-${index}`} item={item} index={index} />
        ))}
      </div>
    </div>
  );
}
