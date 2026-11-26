'use client';

import { Thread, type ThreadComponents } from '@/components/assistant-ui/elements/thread.aui';
import { ThreadList } from '@/components/assistant-ui/thread-list';
import { attachmentLabel, DocumentAttachmentAdapter } from '@/components/chat/document-attachment-adapter';
import { ReasoningSteps } from '@/components/assistant-ui/reasoning-steps';
import { ChatWelcome } from '@/components/chat/chat-welcome';
import { DocumentPanel } from '@/components/chat/document-panel';
import { dbThreadListAdapter } from '@/components/chat/db-thread-list-adapter';
import { DevToolsModal } from '@assistant-ui/react-devtools';
import { streamChatTurn } from '@/lib/chat/stream';
import { getErrorMessage, isApiError } from '@/lib/api-error';
import {
  TurnAccumulator,
  convertChatMessage,
  userMessage,
  type ChatAttachmentMeta,
  type ChatMessage,
} from '@/lib/chat/turn';
import {
  FOLLOW_INTERVAL_MS,
  fetchThreadMessages,
  followThread,
  hasReplyTo,
  threadMessagesQueryKey,
  threadRunningQueryKey,
} from '@/lib/chat/follow';
import { cancelChatTurnApiChatThreadsThreadIdCancelPost, type ChatAttachment } from '@/lib/generated-api';
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
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

// Stateless; one shared instance is fine.
const attachmentAdapter = new DocumentAttachmentAdapter();

// Module scope, so Thread's message subtrees don't re-render with this component.
const THREAD_COMPONENTS: ThreadComponents = { Welcome: ChatWelcome, ReasoningGroup: ReasoningSteps };

function messageText(message: AppendMessage): string {
  return message.content.map((part) => (part.type === 'text' ? part.text : '')).join('');
}

type TurnAttachment = ChatAttachmentMeta & { text: string };

function messageAttachments(message: AppendMessage): TurnAttachment[] {
  return (message.attachments ?? []).flatMap((attachment): TurnAttachment[] => {
    const labelled = attachment.content.map((part) => (part.type === 'text' ? part.text : '')).join('');
    const label = attachmentLabel(attachment.name);
    const text = labelled.startsWith(label) ? labelled.slice(label.length) : labelled;
    return text ? [{ name: attachment.name, text }] : [];
  });
}

/**
 * The runtime for one thread. History is the checkpointer's, fetched from the
 * backend; the turn in flight is accumulated locally from the stream and
 * replaced by the server's copy once the turn is over. The turn runs on the
 * server whether or not this page listens: a turn this page isn't streaming (one
 * running before a reload, or whose stream ended early) is followed by polling
 * the stored history until it ends. Editing and regenerating
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
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const runtimeRef = useRef<AssistantRuntime | null>(null);
  // A turn whose stream was lost (a dropped connection, not a refusal or an agent
  // error) may still be running on the server. Its failure placeholder goes once
  // the server shows the turn running or answered.
  const lostStreamRef = useRef<{ userId: string; ids: Set<string> } | null>(null);

  const followTurn = async (threadId: string): Promise<boolean> => {
    const running = await followThread(queryClient, threadId);
    const lost = lostStreamRef.current;
    const stored = queryClient.getQueryData<ChatMessage[]>(threadMessagesQueryKey(threadId));
    if (lost && (running || hasReplyTo(stored, lost.userId))) {
      lostStreamRef.current = null;
      setInflight((current) => current.filter((message) => !message.id || !lost.ids.has(message.id)));
    }
    return running;
  };

  const remoteRunning = useQuery({
    enabled: remoteId !== undefined && !isStreaming,
    queryKey: threadRunningQueryKey(remoteId),
    queryFn: () => followTurn(remoteId!),
    // Every time a stream ends, ask again: a cached "idle" may predate the turn.
    staleTime: 0,
    refetchInterval: (query) => (query.state.data ? FOLLOW_INTERVAL_MS : false),
  });
  const isRunning = isStreaming || remoteRunning.data === true;

  // A message both stored and still held locally (a stopped turn the server went
  // on to store) is shown once, from the store.
  const messages = useMemo(() => {
    const stored = history.data ?? [];
    const storedIds = new Set(stored.map((message) => message.id));
    return [...stored, ...inflight.filter((message) => !message.id || !storedIds.has(message.id))];
  }, [history.data, inflight]);
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
      setIsStreaming(true);
    });
    const { remoteId: threadId } = await aui.threadListItem().initialize();

    let completed = false;
    let detached = false;
    let agentFailed = false;
    lostStreamRef.current = null;
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
        if (event.t === 'detached') {
          detached = true;
          break;
        }
        setInflight(turn.apply(event));
        if (event.t === 'error') {
          agentFailed = true;
          throw new Error(event.v);
        }
      }
      completed = true;
    } catch (error) {
      if (controller.signal.aborted) setInflight(turn.cancel());
      else {
        setInflight(turn.fail(getErrorMessage(error, 'The turn failed.')));
        if (!agentFailed && !isApiError(error)) {
          lostStreamRef.current = { userId: user.id, ids: new Set(turn.assistantMessages.flatMap((m) => m.id ?? [])) };
        }
      }
    } finally {
      // The server's copy of the turn replaces the local one, in a single render:
      // both carry the same ids, and a render showing both at once would make
      // the runtime re-parent the messages. After a cancel or a failure the user
      // message is already stored, so only the assistant side stays local, with
      // its status showing what happened.
      const stored = await fetchThreadMessages(threadId).catch(() => null);
      if (stored) queryClient.setQueryData(threadMessagesQueryKey(threadId), stored);
      // A detached turn keeps what streamed: the store may not hold it yet, and
      // `messages` drops each local copy once the history has it.
      setInflight(completed && !detached && stored ? [] : turn.assistantMessages);
      // A detached turn is still running: keep showing it, and follow the history.
      // After a clean end the turn was over before `stored` was read; otherwise
      // the page no longer knows, and the next check reads the history again.
      if (detached) queryClient.setQueryData(threadRunningQueryKey(threadId), true);
      else if (!completed) queryClient.removeQueries({ queryKey: threadRunningQueryKey(threadId) });
      setIsStreaming(false);
    }
  };

  // Aborting the stream only stops listening; the turn itself is stopped on the
  // server, from whichever worker runs it.
  const onCancel = async () => {
    abortRef.current?.abort();
    if (!remoteId) return;
    await cancelChatTurnApiChatThreadsThreadIdCancelPost({ path: { thread_id: remoteId } }).catch(() => undefined);
    await queryClient.invalidateQueries({ queryKey: threadRunningQueryKey(remoteId) });
  };

  const runtime = useExternalStoreRuntime({
    isRunning,
    isLoading: history.isLoading,
    messages: threadMessages,
    onNew,
    onCancel,
    adapters: { attachments: attachmentAdapter },
  });
  useLayoutEffect(() => {
    runtimeRef.current = runtime;
  });
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
          <Thread components={THREAD_COMPONENTS} />
        </div>
        <aside className="hidden w-96 shrink-0 flex-col border-l lg:flex">
          <DocumentPanel />
        </aside>
      </AssistantRuntimeProvider>
    </div>
  );
}
