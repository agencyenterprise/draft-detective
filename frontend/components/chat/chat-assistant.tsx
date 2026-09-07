'use client';

import { Thread } from '@/components/assistant-ui/thread';
import { ThreadList } from '@/components/assistant-ui/thread-list';
import { DocumentAttachmentAdapter } from '@/components/chat/document-attachment-adapter';
import { DocumentPanel } from '@/components/chat/document-panel';
import { dbThreadListAdapter } from '@/components/chat/db-thread-list-adapter';
import { DevToolsModal } from '@assistant-ui/react-devtools';
import { DEFAULT_MODEL_ID } from '@/lib/chat-models';
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

/**
 * Per-thread message history backed by chat_messages (via the generated `/chat`
 * SDK). Bound to the active thread via `aui.threadListItem()`; requests are
 * authenticated by the shared generated client configured in `ApiConfig`.
 */
function createHistoryAdapter(aui: ReturnType<typeof useAui>): ThreadHistoryAdapter {
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

// One NDJSON event from /api/chat.
type StreamEvent =
  | { t: 'text'; v: string }
  | { t: 'reasoning'; v: string }
  | { t: 'tool'; id: string; name: string; args?: Record<string, unknown> }
  | { t: 'tool_result'; id: string; result: unknown; isError?: boolean }
  | { t: 'error'; v: string };

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

const chatAdapter: ChatModelAdapter = {
  async *run({ messages, context, abortSignal }) {
    // The Model Selector (in the composer) publishes the chosen model into the
    // run's ModelContext as `config.modelName`.
    const model = context.config?.modelName ?? DEFAULT_MODEL_ID;

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages: messages.map((message) => ({
          role: message.role,
          content: messageToText(message),
        })),
      }),
      signal: abortSignal,
    });

    if (!response.ok || !response.body) {
      const detail = await response.text().catch(() => '');
      throw new Error(detail || `Chat request failed with status ${response.status}`);
    }

    const parts: StreamPart[] = [];

    const applyEvent = (event: StreamEvent) => {
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
          const call = parts.find((p) => p.type === 'tool-call' && p.toolCallId === event.id);
          if (call?.type === 'tool-call') {
            call.result = event.result;
            if (event.isError) call.isError = true;
          }
          break;
        }
        case 'error':
          throw new Error(event.v);
      }
    };

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const drainLines = (flush: boolean) => {
      let newlineIndex: number;
      while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        if (line) applyEvent(JSON.parse(line) as StreamEvent);
      }
      if (flush && buffer.trim()) {
        applyEvent(JSON.parse(buffer.trim()) as StreamEvent);
        buffer = '';
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      drainLines(false);
      yield { content: parts } as ChatModelRunResult;
    }
    drainLines(true);
    yield { content: parts } as ChatModelRunResult;
  },
};

// Per-thread runtime. History + attachments are attached here (not via the
// adapter's unstable_Provider) because the remote-thread-list runtime invokes
// this hook outside that provider, so context adapters wouldn't reach it.
function useChatThreadRuntime() {
  const aui = useAui();

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
