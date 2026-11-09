import type { QueryClient } from '@tanstack/react-query';
import { getThreadApiChatThreadsThreadIdGet, listMessagesApiChatThreadsThreadIdMessagesGet } from '@/lib/generated-api';
import type { ChatMessage } from '@/lib/chat/turn';

/** How often the page checks on a turn it isn't streaming (one started elsewhere, or detached). */
export const FOLLOW_INTERVAL_MS = 3000;

export const threadMessagesQueryKey = (threadId: string | undefined) =>
  ['chat', 'thread', threadId, 'messages'] as const;

/** Whether a turn is running on the thread, as last seen; `true` keeps the page polling. */
export const threadRunningQueryKey = (threadId: string | undefined) => ['chat', 'thread', threadId, 'running'] as const;

/**
 * Whether the stored history has an answer to the user message `userId`: something
 * stored after it. A turn whose stream was lost may have answered all the same.
 */
export function hasReplyTo(stored: ChatMessage[] | undefined, userId: string): boolean {
  const at = stored?.findIndex((message) => message.id === userId) ?? -1;
  return at >= 0 && at < stored!.length - 1;
}

export async function fetchThreadMessages(threadId: string): Promise<ChatMessage[]> {
  return (await listMessagesApiChatThreadsThreadIdMessagesGet({ path: { thread_id: threadId } })) as ChatMessage[];
}

/**
 * One check on a thread's turn, for a turn this page isn't streaming: one started
 * before a reload, in another tab, or whose stream ended while it ran on.
 *
 * The history is refreshed from the checkpointer while the turn runs, once more
 * after it ends, and whenever the page doesn't know the thread was idle before
 * (a first check, or one after a stream that didn't end cleanly): a history read
 * then may predate the turn's end. The thread is read first, so the history read
 * after it says "not running" is the final one. A history request already in
 * flight may predate the turn's end too, so it is cancelled rather than allowed
 * to overwrite this one.
 */
export async function followThread(queryClient: QueryClient, threadId: string): Promise<boolean> {
  const knownIdle = queryClient.getQueryData<boolean>(threadRunningQueryKey(threadId)) === false;
  const thread = await getThreadApiChatThreadsThreadIdGet({ path: { thread_id: threadId } });
  if (!thread.is_running && knownIdle) return false;
  const key = threadMessagesQueryKey(threadId);
  await queryClient.cancelQueries({ queryKey: key });
  queryClient.setQueryData(key, await fetchThreadMessages(threadId));
  return thread.is_running;
}
