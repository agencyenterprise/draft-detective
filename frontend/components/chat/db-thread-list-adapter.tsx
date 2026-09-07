import {
  createThreadApiChatThreadsPost,
  deleteThreadApiChatThreadsThreadIdDelete,
  generateThreadTitleApiChatThreadsThreadIdTitlePost,
  listThreadsApiChatThreadsGet,
  updateThreadApiChatThreadsThreadIdPatch,
  type ChatThreadResponse,
} from '@/lib/generated-api';
import { type RemoteThreadListAdapter } from '@assistant-ui/react';
import { createAssistantStream } from 'assistant-stream';

function toMetadata(thread: ChatThreadResponse) {
  return {
    status: thread.is_archived ? ('archived' as const) : ('regular' as const),
    remoteId: thread.id,
    title: thread.title ?? undefined,
  };
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
    const simpleMessages = messages
      .map((message) => ({
        role: message.role,
        content: message.content.map((part) => (part.type === 'text' ? part.text : '')).join(''),
      }))
      .filter((message) => message.content);

    // The backend generates the title and stores it on the thread in one call,
    // so it survives reloads without a second request from here.
    let title = 'New chat';
    try {
      const thread = await generateThreadTitleApiChatThreadsThreadIdTitlePost({
        path: { thread_id: remoteId },
        body: { messages: simpleMessages },
      });
      title = thread.title ?? title;
    } catch {
      // fall back to the default title
    }
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
