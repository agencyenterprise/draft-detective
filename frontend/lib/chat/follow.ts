import type { QueryClient } from '@tanstack/react-query';
import { getThreadApiChatThreadsThreadIdGet, listMessagesApiChatThreadsThreadIdMessagesGet } from '@/lib/generated-api';
import type { ChatMessage } from '@/lib/chat/turn';

/** How often the page checks on a turn it isn't streaming (one started elsewhere, or detached). */
export const FOLLOW_INTERVAL_MS = 3000;

export const threadMessagesQueryKey = (threadId: string | undefined) =>
  ['chat', 'thread', threadId, 'messages'] as const;

/** Whether a turn is running on the thread, as last seen; `true` keeps the page polling. */
export const threadRunningQueryKey = (threadId: string | undefined) => ['chat', 'thread', threadId, 'running'] as const;

export async function fetchThreadMessages(threadId: string): Promise<ChatMessage[]> {
  return (await listMessagesApiChatThreadsThreadIdMessagesGet({ path: { thread_id: threadId } })) as ChatMessage[];
}

/**
 * One check on a thread's turn, for a turn this page isn't streaming: one started
 * before a reload, in another tab, or whose stream ended while it ran on.
 *
 * Every check refreshes the history from the checkpointer. The thread is read
 * first, so the history read after it says "not running" is the final one. A
 * history request already in flight was sent earlier and may predate the turn's
 * end, so it is cancelled rather than allowed to overwrite this one.
 */
export async function followThread(queryClient: QueryClient, threadId: string): Promise<boolean> {
  const thread = await getThreadApiChatThreadsThreadIdGet({ path: { thread_id: threadId } });
  const key = threadMessagesQueryKey(threadId);
  await queryClient.cancelQueries({ queryKey: key });
  queryClient.setQueryData(key, await fetchThreadMessages(threadId));
  return thread.is_running;
}
