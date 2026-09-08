'use client';

import { Thread } from '@/components/assistant-ui/thread';
import { ThreadList } from '@/components/assistant-ui/thread-list';
import { DocumentAttachmentAdapter } from '@/components/chat/document-attachment-adapter';
import { DocumentPanel } from '@/components/chat/document-panel';
import { dbThreadListAdapter } from '@/components/chat/db-thread-list-adapter';
import { DevToolsModal } from '@assistant-ui/react-devtools';
import { streamChatTurn } from '@/lib/chat/stream';
import {
  TurnAccumulator,
  convertChatMessage,
  userMessage,
  type ChatAttachmentMeta,
  type ChatMessage,
} from '@/lib/chat/turn';
import { listMessagesApiChatThreadsThreadIdMessagesGet, type ChatAttachment } from '@/lib/generated-api';
import {
  AssistantRuntimeProvider,
  useAui,
  useAuiState,
  useExternalMessageConverter,
  useExternalStoreRuntime,
  useRemoteThreadListRuntime,
  type AppendMessage,
  type AssistantRuntime,
} from '@assistant-ui/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

// Stateless; one shared instance is fine.
const attachmentAdapter = new DocumentAttachmentAdapter();

export const threadMessagesQueryKey = (threadId: string | undefined) =>
  ['chat', 'thread', threadId, 'messages'] as const;

// The attachment adapter stores extracted text as `Attached document "<name>":\n\n<text>`.
const ATTACHMENT_PREFIX = /^Attached document "[^"]*":\n\n/;

async function fetchThreadMessages(threadId: string): Promise<ChatMessage[]> {
  return (await listMessagesApiChatThreadsThreadIdMessagesGet({ path: { thread_id: threadId } })) as ChatMessage[];
}

function messageText(message: AppendMessage): string {
  return message.content.map((part) => (part.type === 'text' ? part.text : '')).join('');
}

type TurnAttachment = ChatAttachmentMeta & { text: string };

function messageAttachments(message: AppendMessage): TurnAttachment[] {
  return (message.attachments ?? []).flatMap((attachment): TurnAttachment[] => {
    const text = attachment.content
      .map((part) => (part.type === 'text' ? part.text : ''))
      .join('')
      .replace(ATTACHMENT_PREFIX, '');
    return text ? [{ name: attachment.name, text }] : [];
  });
}

/**
 * The runtime for one thread. History is the checkpointer's, fetched from the
 * backend; the turn in flight is accumulated locally from the stream and
 * replaced by the server's copy once the turn is over. Editing and regenerating
 * are not offered: with server-owned history they would mean forking a
 * checkpoint, which this page does not do yet.
 */
function useChatThreadRuntime(): AssistantRuntime {
  const aui = useAui();
  const remoteId = useAuiState((state) => state.threadListItem.remoteId);
  const queryClient = useQueryClient();

  const history = useQuery({
    enabled: remoteId !== undefined,
    queryKey: threadMessagesQueryKey(remoteId),
    queryFn: () => fetchThreadMessages(remoteId!),
    // Only a turn changes a thread, and turns refresh the data themselves.
    staleTime: Infinity,
  });

  const [inflight, setInflight] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const runtimeRef = useRef<AssistantRuntime | null>(null);

  const messages = useMemo(() => [...(history.data ?? []), ...inflight], [history.data, inflight]);
  const threadMessages = useExternalMessageConverter({ callback: convertChatMessage, messages, isRunning });

  const onNew = async (message: AppendMessage) => {
    const text = messageText(message);
    const attachments = messageAttachments(message);
    // The Model Selector (in the composer) publishes the chosen model into the ModelContext.
    const model = runtimeRef.current?.thread.getModelContext().config?.modelName;

    const controller = new AbortController();
    abortRef.current = controller;
    const user = userMessage(text, attachments);
    const turn = new TurnAccumulator(user);
    // Rendered before the thread is initialised, on purpose: the runtime marks a
    // thread initialised when it first has messages, and assistant-ui titles a
    // new thread only if it is still "new" at that moment. Initialising first
    // would take that over and leave the thread untitled.
    flushSync(() => {
      setInflight(turn.messages);
      setIsRunning(true);
    });
    const { remoteId: threadId } = await aui.threadListItem().initialize();

    let completed = false;
    try {
      const events = streamChatTurn({
        threadId,
        model,
        message: text,
        messageId: user.id,
        attachments: attachments.map(({ name, text: content }): ChatAttachment => ({ name, text: content })),
        signal: controller.signal,
      });
      for await (const event of events) {
        setInflight(turn.apply(event));
        if (event.t === 'error') throw new Error(event.v);
      }
      completed = true;
    } catch (error) {
      if (controller.signal.aborted) setInflight(turn.cancel());
      else setInflight(turn.fail(error instanceof Error ? error.message : 'The turn failed.'));
    } finally {
      // The server's copy of the turn replaces the local one, in a single render:
      // both carry the same ids, and a render showing both at once would make
      // the runtime re-parent the messages. After a cancel or a failure the user
      // message is already stored, so only the assistant side stays local, with
      // its status showing what happened.
      const stored = await fetchThreadMessages(threadId).catch(() => null);
      if (stored) queryClient.setQueryData(threadMessagesQueryKey(threadId), stored);
      setInflight(completed && stored ? [] : turn.assistantMessages);
      setIsRunning(false);
    }
  };

  const runtime = useExternalStoreRuntime({
    isRunning,
    isLoading: history.isLoading,
    messages: threadMessages,
    onNew,
    onCancel: async () => abortRef.current?.abort(),
    adapters: { attachments: attachmentAdapter },
  });
  runtimeRef.current = runtime;
  return runtime;
}

export function ChatAssistant() {
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: useChatThreadRuntime,
    adapter: dbThreadListAdapter,
  });

  return (
    // Full-bleed: fills the width and whatever height the shell leaves below the app bar.
    <div className="flex min-h-0 w-full flex-1 overflow-hidden bg-background">
      <AssistantRuntimeProvider runtime={runtime}>
        {/* Dev-only inspector launcher (stripped from production builds). */}
        <DevToolsModal />
        <aside className="hidden w-64 shrink-0 flex-col border-r p-2 sm:flex">
          <ThreadList />
        </aside>
        <div className="min-w-0 flex-1">
          <Thread />
        </div>
        <aside className="hidden w-96 shrink-0 flex-col border-l lg:flex">
          <DocumentPanel />
        </aside>
      </AssistantRuntimeProvider>
    </div>
  );
}
