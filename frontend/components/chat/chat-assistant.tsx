'use client';

import { Thread } from '@/components/assistant-ui/thread';
import { ThreadList } from '@/components/assistant-ui/thread-list';
import { DocumentAttachmentAdapter } from '@/components/chat/document-attachment-adapter';
import { DocumentPanel } from '@/components/chat/document-panel';
import { dbThreadListAdapter } from '@/components/chat/db-thread-list-adapter';
import { DevToolsModal } from '@assistant-ui/react-devtools';
import { streamChatTurn, type ChatStreamEvent } from '@/lib/chat/stream';
import {
  appendMessageApiChatThreadsThreadIdMessagesPost,
  listMessagesApiChatThreadsThreadIdMessagesGet,
} from '@/lib/generated-api';
import {
  AssistantRuntimeProvider,
  useAui,
  useLocalRuntime,
  useRemoteThreadListRuntime,
  type ChatModelAdapter,
  type ChatModelRunResult,
  type ThreadHistoryAdapter,
  type ThreadMessage,
} from '@assistant-ui/react';
import { useMemo } from 'react';

// Stateless; one shared instance is fine.
const attachmentAdapter = new DocumentAttachmentAdapter();

type HistoryLoadResult = Awaited<ReturnType<ThreadHistoryAdapter['load']>>;

type Aui = ReturnType<typeof useAui>;

/**
 * Per-thread message history backed by chat_messages (via the generated `/chat`
 * SDK). Bound to the active thread via `aui.threadListItem()`; requests are
 * authenticated by the shared generated client configured in `ApiConfig`.
 */
function createHistoryAdapter(aui: Aui): ThreadHistoryAdapter {
  return {
    async load() {
      const remoteId = aui.threadListItem().getState().remoteId;
      if (!remoteId) return { messages: [] };
      const rows = await listMessagesApiChatThreadsThreadIdMessagesGet({ path: { thread_id: remoteId } });
      // Each row's `content` is the ExportedMessageRepositoryItem we stored.
      return { messages: rows.map((row) => row.content) } as HistoryLoadResult;
    },
    async append(item) {
      const { remoteId } = await aui.threadListItem().initialize();
      await appendMessageApiChatThreadsThreadIdMessagesPost({
        path: { thread_id: remoteId },
        body: {
          message_id: item.message.id,
          parent_id: item.parentId,
          content: item as unknown as { [key: string]: unknown },
        },
      });
    },
  };
}

// Mutable parts we accumulate while streaming; yielded as assistant-ui content.
type StreamPart =
  | { type: 'text'; text: string }
  | { type: 'reasoning'; text: string }
  | {
      type: 'tool-call';
      toolCallId: string;
      toolName: string;
      args: Record<string, unknown>;
      argsText: string;
      result?: unknown;
      isError?: boolean;
    };

/**
 * Flatten an assistant-ui message into plain text for the API, including the
 * text extracted from any attached documents (which the attachment adapter
 * stores as text parts on `message.attachments`).
 */
function messageToText(message: ThreadMessage): string {
  const bodyText = message.content.map((part) => (part.type === 'text' ? part.text : '')).join('');

  const attachmentText = (message.attachments ?? [])
    .flatMap((attachment) => attachment.content)
    .map((part) => (part.type === 'text' ? part.text : ''))
    .filter(Boolean)
    .join('\n\n');

  return [attachmentText, bodyText].filter(Boolean).join('\n\n');
}

function applyEvent(parts: StreamPart[], event: ChatStreamEvent): void {
  const last = parts[parts.length - 1];
  switch (event.t) {
    case 'text':
      if (last?.type === 'text') last.text += event.v;
      else parts.push({ type: 'text', text: event.v });
      break;
    case 'reasoning':
      if (last?.type === 'reasoning') last.text += event.v;
      else parts.push({ type: 'reasoning', text: event.v });
      break;
    case 'tool':
      parts.push({
        type: 'tool-call',
        toolCallId: event.id,
        toolName: event.name,
        args: event.args ?? {},
        argsText: JSON.stringify(event.args ?? {}),
      });
      break;
    case 'tool_result': {
      const call = parts.find((part) => part.type === 'tool-call' && part.toolCallId === event.id);
      if (call?.type === 'tool-call') {
        call.result = event.result;
        if (event.isError) call.isError = true;
      }
      break;
    }
    case 'error':
      throw new Error(event.v);
  }
}

/**
 * Streams each turn from the backend's chat agent. The thread is initialized
 * first so the backend can scope the run (and its tracing) to the thread id.
 */
function createChatAdapter(aui: Aui): ChatModelAdapter {
  return {
    async *run({ messages, context, abortSignal }) {
      const { remoteId } = await aui.threadListItem().initialize();
      const parts: StreamPart[] = [];

      const events = streamChatTurn({
        threadId: remoteId,
        // The Model Selector (in the composer) publishes the chosen model into
        // the run's ModelContext as `config.modelName`.
        model: context.config?.modelName,
        messages: messages.map((message) => ({ role: message.role, content: messageToText(message) })),
        signal: abortSignal,
      });

      for await (const event of events) {
        applyEvent(parts, event);
        yield { content: parts } as ChatModelRunResult;
      }
      yield { content: parts } as ChatModelRunResult;
    },
  };
}

// Per-thread runtime. History + attachments are attached here (not via the
// adapter's unstable_Provider) because the remote-thread-list runtime invokes
// this hook outside that provider, so context adapters wouldn't reach it.
function useChatThreadRuntime() {
  const aui = useAui();

  const chatAdapter = useMemo(() => createChatAdapter(aui), [aui]);
  const adapters = useMemo(() => ({ history: createHistoryAdapter(aui), attachments: attachmentAdapter }), [aui]);

  return useLocalRuntime(chatAdapter, { adapters });
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
