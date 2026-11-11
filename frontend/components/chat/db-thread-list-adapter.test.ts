import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ThreadMessage } from '@assistant-ui/react';
import type { AssistantStream } from 'assistant-stream';
import {
  createThreadApiChatThreadsPost,
  deleteThreadApiChatThreadsThreadIdDelete,
  generateThreadTitleApiChatThreadsThreadIdTitlePost,
  listThreadsApiChatThreadsGet,
  updateThreadApiChatThreadsThreadIdPatch,
  type ChatThreadResponse,
} from '@/lib/generated-api';
import { dbThreadListAdapter as adapter } from './db-thread-list-adapter';

vi.mock('@/lib/generated-api', () => ({
  createThreadApiChatThreadsPost: vi.fn(),
  deleteThreadApiChatThreadsThreadIdDelete: vi.fn(),
  generateThreadTitleApiChatThreadsThreadIdTitlePost: vi.fn(),
  listThreadsApiChatThreadsGet: vi.fn(),
  updateThreadApiChatThreadsThreadIdPatch: vi.fn(),
}));

const createThread = vi.mocked(createThreadApiChatThreadsPost);
const deleteThread = vi.mocked(deleteThreadApiChatThreadsThreadIdDelete);
const generateTitle = vi.mocked(generateThreadTitleApiChatThreadsThreadIdTitlePost);
const listThreads = vi.mocked(listThreadsApiChatThreadsGet);
const updateThread = vi.mocked(updateThreadApiChatThreadsThreadIdPatch);

function row(id: string, fields: Partial<ChatThreadResponse> = {}): ChatThreadResponse {
  return { id, title: null, is_archived: false, ...fields } as ChatThreadResponse;
}

type Part = { type: 'text'; text: string } | { type: 'image'; image: string };

function message(role: 'user' | 'assistant', ...content: Part[]): ThreadMessage {
  return { role, content } as unknown as ThreadMessage;
}

/** The text the title stream hands assistant-ui. */
async function textOf(stream: AssistantStream): Promise<string> {
  let text = '';
  for await (const chunk of stream) {
    if (chunk.type === 'text-delta') text += chunk.textDelta;
  }
  return text;
}

async function titleFor(remoteId: string, messages: ThreadMessage[] = []): Promise<string> {
  return textOf(await adapter.generateTitle(remoteId, messages));
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe('dbThreadListAdapter thread metadata', () => {
  it('lists archived and regular threads, leaving untitled ones without a title', async () => {
    listThreads.mockResolvedValue([row('a', { title: 'Budget' }), row('b', { is_archived: true })] as never);

    const { threads } = await adapter.list();

    expect(threads).toEqual([
      { status: 'regular', remoteId: 'a', title: 'Budget' },
      { status: 'archived', remoteId: 'b', title: undefined },
    ]);
  });

  it('creates an untitled thread and hands back its id', async () => {
    createThread.mockResolvedValue(row('new') as never);

    await expect(adapter.initialize('local-id')).resolves.toEqual({ remoteId: 'new', externalId: undefined });
    expect(createThread).toHaveBeenCalledWith({ body: { title: null } });
  });

  it('fetches one thread from the list', async () => {
    listThreads.mockResolvedValue([row('a'), row('b', { title: 'Methods', is_archived: true })] as never);

    await expect(adapter.fetch('b')).resolves.toEqual({ status: 'archived', remoteId: 'b', title: 'Methods' });
  });

  it('fails to fetch a thread the backend no longer lists', async () => {
    listThreads.mockResolvedValue([row('a')] as never);

    await expect(adapter.fetch('gone')).rejects.toThrow('Thread not found');
  });

  it.each([
    ['rename', () => adapter.rename('t1', 'Draft review'), { title: 'Draft review' }],
    ['archive', () => adapter.archive('t1'), { is_archived: true }],
    ['unarchive', () => adapter.unarchive?.('t1'), { is_archived: false }],
  ])('%s updates only the matching field', async (_name, run, body) => {
    await run();

    expect(updateThread).toHaveBeenCalledExactlyOnceWith({ path: { thread_id: 't1' }, body });
  });

  it('deletes the thread', async () => {
    await adapter.delete('t1');

    expect(deleteThread).toHaveBeenCalledExactlyOnceWith({ path: { thread_id: 't1' } });
  });
});

describe('dbThreadListAdapter.generateTitle', () => {
  it('sends only the text of each message and drops messages with none', async () => {
    generateTitle.mockResolvedValue(row('t1', { title: 'Sampling bias' }) as never);

    const title = await titleFor('t1', [
      message('user', { type: 'text', text: 'Check ' }, { type: 'image', image: 'x' }, { type: 'text', text: 'this' }),
      message('assistant', { type: 'image', image: 'y' }),
      message('assistant', { type: 'text', text: 'Done.' }),
    ]);

    expect(title).toBe('Sampling bias');
    expect(generateTitle).toHaveBeenCalledWith({
      path: { thread_id: 't1' },
      body: {
        messages: [
          { role: 'user', content: 'Check this' },
          { role: 'assistant', content: 'Done.' },
        ],
      },
    });
  });

  it('asks the backend once when assistant-ui requests the same title twice at once', async () => {
    let resolve: (thread: ChatThreadResponse) => void = () => {};
    generateTitle.mockReturnValue(new Promise((r) => (resolve = r)) as never);

    const first = titleFor('t1');
    const second = titleFor('t1');
    resolve(row('t1', { title: 'Shared' }));

    await expect(Promise.all([first, second])).resolves.toEqual(['Shared', 'Shared']);
    expect(generateTitle).toHaveBeenCalledTimes(1);
  });

  it('keeps concurrent requests for different threads apart', async () => {
    const resolvers: ((thread: ChatThreadResponse) => void)[] = [];
    generateTitle.mockImplementation(() => new Promise((r) => resolvers.push(r)) as never);

    const first = titleFor('t1');
    const second = titleFor('t2');
    resolvers[0](row('t1', { title: 'First' }));
    resolvers[1](row('t2', { title: 'Second' }));

    await expect(Promise.all([first, second])).resolves.toEqual(['First', 'Second']);
    expect(generateTitle.mock.calls.map(([options]) => options.path.thread_id)).toEqual(['t1', 't2']);
  });

  it('asks again once the earlier request has settled', async () => {
    generateTitle.mockResolvedValue(row('t1', { title: 'Title' }) as never);

    await titleFor('t1');
    await titleFor('t1');

    expect(generateTitle).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['the request fails', () => generateTitle.mockRejectedValue(new Error('500'))],
    ['the backend returns no title', () => generateTitle.mockResolvedValue(row('t1') as never)],
  ])('falls back to "New chat" when %s', async (_case, arrange) => {
    arrange();

    await expect(titleFor('t1')).resolves.toBe('New chat');
  });

  it('retries after a failed request instead of reusing it', async () => {
    generateTitle.mockRejectedValueOnce(new Error('500'));
    generateTitle.mockResolvedValueOnce(row('t1', { title: 'Second try' }) as never);

    await expect(titleFor('t1')).resolves.toBe('New chat');
    await expect(titleFor('t1')).resolves.toBe('Second try');
  });
});
