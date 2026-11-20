'use client';

import { getErrorDetail, isApiError } from '@/lib/api-error';
import { fetchThreadMessages, FOLLOW_INTERVAL_MS } from '@/lib/chat/follow';
import { streamChatTurn } from '@/lib/chat/stream';
import type { ChatMessage } from '@/lib/chat/turn';
import {
  cancelChatTurnApiChatThreadsThreadIdCancelPost,
  createThreadApiChatThreadsPost,
  extractAttachmentTextApiChatExtractPost,
  getThreadApiChatThreadsThreadIdGet,
  listLiveReportFilesApiLiveReportsThreadIdFilesGet,
} from '@/lib/generated-api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { MESSAGES, stepOf } from './live-report-state';

export const liveReportKey = (threadId: string | null) => ['live-report', threadId] as const;

/** Stands for the report being started, before its thread exists. */
const NEW = 'new';

/** The text of a stored message: a string, or its text blocks joined. */
export function messageText(message: ChatMessage): string {
  const { content } = message;
  if (typeof content === 'string') return content;
  return content.map((block) => ('text' in block && typeof block.text === 'string' ? block.text : '')).join('');
}

/**
 * Why a report can't be shown: it doesn't exist (or isn't a live report), or
 * reading it failed and may work on a retry. Never shown as an empty report.
 */
export function loadFailure(error: Error | null, kind: string | undefined): 'not-found' | 'error' | null {
  if (isApiError(error, 404) || (kind !== undefined && kind !== 'live_report')) return 'not-found';
  return error ? 'error' : null;
}

/** The person's messages and the agent's replies to them, without tool traffic. */
export interface ConversationEntry {
  from: 'you' | 'agent';
  text: string;
}

export function conversationOf(messages: ChatMessage[]): ConversationEntry[] {
  return messages.flatMap((message): ConversationEntry[] => {
    const text = messageText(message).trim();
    if (!text) return [];
    if (message.type === 'human') return [{ from: 'you', text }];
    if (message.type === 'ai' && !message.tool_calls?.length) return [{ from: 'agent', text }];
    return [];
  });
}

/**
 * One live report: its files, its hidden conversation, and the actions the
 * buttons take on it. While the agent works the page polls, so files appear as
 * they are written, including each research note.
 */
export function useLiveReport(threadId: string | null) {
  const queryClient = useQueryClient();
  // The layout keeps this hook mounted from one report to the next, so a turn's
  // state is kept by the report it belongs to: opening another report mid-turn
  // must not show this one's turn or its error there.
  const [sendingFor, setSendingFor] = useState<ReadonlySet<string>>(new Set());
  const [errors, setErrors] = useState<Readonly<Record<string, string>>>({});
  const key = threadId ?? NEW;
  const enabled = threadId !== null;

  const setSending = (id: string, on: boolean) =>
    setSendingFor((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const setError = (id: string, text: string | null) =>
    setErrors((prev) => {
      const next = { ...prev };
      if (text === null) delete next[id];
      else next[id] = text;
      return next;
    });

  const threadKey = [...liveReportKey(threadId), 'thread'] as const;
  const thread = useQuery({
    queryKey: threadKey,
    queryFn: async () => {
      const wasRunning = queryClient.getQueryData<{ is_running: boolean }>(threadKey)?.is_running;
      const next = await getThreadApiChatThreadsThreadIdGet({ path: { thread_id: threadId! } });
      // The turn just ended (one this page isn't streaming): read the files and
      // messages once more, since their last poll may predate the turn's end.
      // Not the thread's own key: refetching it from inside its fetch would loop.
      if (wasRunning && !next.is_running) {
        for (const part of ['files', 'messages']) {
          void queryClient.invalidateQueries({ queryKey: [...liveReportKey(threadId), part] });
        }
      }
      return next;
    },
    enabled,
    refetchInterval: (query) => (query.state.data?.is_running ? FOLLOW_INTERVAL_MS : false),
  });
  const working = sendingFor.has(key) || Boolean(thread.data?.is_running);
  const poll = working ? FOLLOW_INTERVAL_MS : false;

  const files = useQuery({
    queryKey: [...liveReportKey(threadId), 'files'],
    queryFn: () => listLiveReportFilesApiLiveReportsThreadIdFilesGet({ path: { thread_id: threadId! } }),
    enabled,
    refetchInterval: poll,
  });
  const messages = useQuery({
    queryKey: [...liveReportKey(threadId), 'messages'],
    queryFn: () => fetchThreadMessages(threadId!),
    enabled,
    refetchInterval: poll,
  });

  const conversation = conversationOf(messages.data ?? []);
  const lastSent = conversation.findLast((m) => m.from === 'you')?.text;
  const lastReply = conversation.at(-1)?.from === 'agent' ? conversation.at(-1)?.text : undefined;
  const fileList = files.data ?? [];

  const refresh = () => queryClient.invalidateQueries({ queryKey: liveReportKey(threadId) });

  /** Send one message into the conversation and wait for the turn to end. */
  async function send(message: string, id = threadId, attachments: { name: string; text: string }[] = []) {
    if (!id) return;
    setSending(id, true);
    setError(id, null);
    try {
      for await (const event of streamChatTurn({ threadId: id, message, attachments })) {
        if (event.t === 'error') setError(id, event.v);
        // Files land in the thread's state as the agent writes them.
        if (event.t === 'tool_result') queryClient.invalidateQueries({ queryKey: [...liveReportKey(id), 'files'] });
      }
    } catch (caught) {
      setError(id, getErrorDetail(caught, 'The agent could not take that message.'));
    } finally {
      setSending(id, false);
      await queryClient.invalidateQueries({ queryKey: liveReportKey(id) });
    }
  }

  return {
    loading: enabled && (thread.isPending || files.isPending || messages.isPending),
    failed: loadFailure(thread.error ?? files.error ?? messages.error, thread.data?.kind),
    /** The report's file name, as the thread was titled when it started. */
    title: thread.data?.title ?? null,
    working,
    error: errors[key] ?? null,
    files: fileList,
    /** The stored messages, tool calls included, for the conversation panel. */
    messages: messages.data ?? [],
    conversation,
    lastReply,
    step: stepOf(fileList, lastSent),
    send: (message: string) => send(message),
    refresh,
    async stop() {
      if (threadId) await cancelChatTurnApiChatThreadsThreadIdCancelPost({ path: { thread_id: threadId } });
      await refresh();
    },
    /** Start a new live report from a document; returns its id once the first turn is sent. */
    async start(file: File, onCreated: (id: string) => void) {
      setError(NEW, null);
      setSending(NEW, true);
      try {
        const { text } = await extractAttachmentTextApiChatExtractPost({ body: { file } });
        const created = await createThreadApiChatThreadsPost({ body: { kind: 'live_report', title: file.name } });
        setSending(NEW, false);
        onCreated(created.id);
        await send(MESSAGES.start, created.id, [{ name: file.name, text }]);
      } catch (caught) {
        setError(NEW, getErrorDetail(caught, `Could not read "${file.name}".`));
        setSending(NEW, false);
      }
    },
  };
}

export type LiveReport = ReturnType<typeof useLiveReport>;
