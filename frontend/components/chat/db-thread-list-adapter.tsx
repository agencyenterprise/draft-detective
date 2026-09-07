import {
  createThreadApiChatThreadsPost,
  deleteThreadApiChatThreadsThreadIdDelete,
  generateThreadTitleApiChatThreadsThreadIdTitlePost,
  listThreadsApiChatThreadsGet,
  updateThreadApiChatThreadsThreadIdPatch,
  type ChatThreadResponse,
} from '@/lib/generated-api';
import { type RemoteThreadListAdapter, type ThreadMessage } from '@assistant-ui/react';
import { createAssistantStream } from 'assistant-stream';

function toMetadata(thread: ChatThreadResponse) {
  return {
    status: thread.is_archived ? ('archived' as const) : ('regular' as const),
    remoteId: thread.id,
    title: thread.title ?? undefined,
  };
}

// assistant-ui can ask for a new thread's title more than once around the end of
// its first run; one request per thread is enough, and both callers get it.
const pendingTitles = new Map<string, Promise<string>>();

function requestTitleOnce(remoteId: string, messages: readonly ThreadMessage[]): Promise<string> {
  const pending = pendingTitles.get(remoteId);
  if (pending) return pending;
  const request = requestTitle(remoteId, messages).finally(() => pendingTitles.delete(remoteId));
  pendingTitles.set(remoteId, request);
  return request;
}

async function requestTitle(remoteId: string, messages: readonly ThreadMessage[]): Promise<string> {
  const simpleMessages = messages
    .map((message) => ({
      role: message.role,
      content: message.content.map((part) => (part.type === 'text' ? part.text : '')).join(''),
    }))
    .filter((message) => message.content);

  // The backend generates the title and stores it on the thread in one call,
  // so it survives reloads without a second request from here.
  try {
    const thread = await generateThreadTitleApiChatThreadsThreadIdTitlePost({
      path: { thread_id: remoteId },
      body: { messages: simpleMessages },
    });
    return thread.title ?? 'New chat';
  } catch {
    return 'New chat';
  }
}

/**
 * Thread-list metadata backed by our Postgres (via the generated `/chat` SDK).
 * Requests are authenticated by the shared generated client (configured in
 * `ApiConfig`), so no token plumbing is needed here. Per-thread message history
 * is provided separately, inside the runtime hook (see `useChatThreadRuntime`
 * in chat-assistant), because the remote-thread-list runtime calls that hook
 * outside this adapter's `unstable_Provider`.
 */
export const dbThreadListAdapter: RemoteThreadListAdapter = {
  list: async () => {
    const threads = await listThreadsApiChatThreadsGet();
    return { threads: threads.map(toMetadata) };
  },
  initialize: async () => {
    const thread = await createThreadApiChatThreadsPost({ body: { title: null } });
    return { remoteId: thread.id, externalId: undefined };
  },
  rename: async (remoteId, newTitle) => {
    await updateThreadApiChatThreadsThreadIdPatch({ path: { thread_id: remoteId }, body: { title: newTitle } });
  },
  archive: async (remoteId) => {
    await updateThreadApiChatThreadsThreadIdPatch({ path: { thread_id: remoteId }, body: { is_archived: true } });
  },
  unarchive: async (remoteId) => {
    await updateThreadApiChatThreadsThreadIdPatch({ path: { thread_id: remoteId }, body: { is_archived: false } });
  },
  delete: async (remoteId) => {
    await deleteThreadApiChatThreadsThreadIdDelete({ path: { thread_id: remoteId } });
  },
  generateTitle: async (remoteId, messages) => {
    const title = await requestTitleOnce(remoteId, messages);
    return createAssistantStream((controller) => {
      controller.appendText(title);
    });
  },
  fetch: async (remoteId) => {
    const threads = await listThreadsApiChatThreadsGet();
    const thread = threads.find((row) => row.id === remoteId);
    if (!thread) throw new Error('Thread not found');
    return toMetadata(thread);
  },
};
