import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, useEffect, useLayoutEffect } from 'react';
import { useAui, type CompleteAttachment, type ThreadMessage } from '@assistant-ui/react';
import { streamChatTurn, type ChatStreamEvent } from '@/lib/chat/stream';
import type { ChatMessage } from '@/lib/chat/turn';
import {
  createThreadApiChatThreadsPost,
  listMessagesApiChatThreadsThreadIdMessagesGet,
  listThreadsApiChatThreadsGet,
} from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { ChatAssistant } from './chat-assistant';

type Aui = ReturnType<typeof useAui>;
const seen: { aui?: Aui } = {};
// The model the composer's selector has chosen, if any.
let modelName: string | undefined;

// The thread view stands in for the composer: it hands the test the runtime and
// publishes the chosen model the way the Model Selector does.
function Probe() {
  const aui = useAui();
  useLayoutEffect(() => {
    seen.aui = aui;
  });
  useEffect(() => {
    if (!modelName) return;
    const config = { config: { modelName } };
    return aui.modelContext().register({ getModelContext: () => config });
  }, [aui]);
  return null;
}

vi.mock('@/components/assistant-ui/elements/thread.aui', () => ({ Thread: Probe }));
vi.mock('@/components/assistant-ui/thread-list', () => ({ ThreadList: () => null }));
vi.mock('@/components/chat/document-panel', () => ({ DocumentPanel: () => null }));
vi.mock('@assistant-ui/react-devtools', () => ({ DevToolsModal: () => null }));
vi.mock('@/lib/chat/stream', () => ({ streamChatTurn: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  createThreadApiChatThreadsPost: vi.fn(),
  listThreadsApiChatThreadsGet: vi.fn(),
  listMessagesApiChatThreadsThreadIdMessagesGet: vi.fn(),
}));

const stream = vi.mocked(streamChatTurn);
const createThread = vi.mocked(createThreadApiChatThreadsPost);
const listThreads = vi.mocked(listThreadsApiChatThreadsGet);
const listMessages = vi.mocked(listMessagesApiChatThreadsThreadIdMessagesGet);

let threadId = '';
let threadCount = 0;
// What the backend has stored for the thread; a turn's stream stores into it.
let stored: ChatMessage[] = [];
let rendered: Rendered | null = null;

type StreamOptions = Parameters<typeof streamChatTurn>[0];

/** The backend's side of a turn: it stores the user message, then streams `events`. */
function serve(events: ChatStreamEvent[], storedReply: ChatMessage[] = []) {
  stream.mockImplementationOnce(async function* (options: StreamOptions) {
    stored = [...stored, { id: options.messageId, type: 'human', content: options.message }];
    for (const event of events) yield event;
    stored = [...stored, ...storedReply];
  });
}

/** A turn whose stream sends `events`, then waits until the user stops it. */
function serveUntilAborted(events: ChatStreamEvent[]) {
  stream.mockImplementationOnce(async function* (options: StreamOptions) {
    stored = [...stored, { id: options.messageId, type: 'human', content: options.message }];
    for (const event of events) yield event;
    await new Promise((_, reject) =>
      options.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))),
    );
  });
}

async function send(text: string, attachments: CompleteAttachment[] = []): Promise<void> {
  await act(async () => {
    seen.aui!.thread().append({ role: 'user', content: [{ type: 'text', text }], attachments });
  });
  await flush();
  await flush();
}

/** What the thread shows: each message's id, role, text and how it ended. */
function shown() {
  const textOf = (message: ThreadMessage) =>
    message.content.map((part) => (part.type === 'text' ? part.text : '')).join('');
  return seen
    .aui!.thread()
    .getState()
    .messages.map((message) => ({
      id: message.id,
      role: message.role,
      text: textOf(message),
      ...(message.role === 'assistant' && message.status.type === 'incomplete' ? { status: message.status } : {}),
    }));
}

const isRunning = () => seen.aui!.thread().getState().isRunning;

const reply = (id: string, text: string): ChatStreamEvent[] => [
  { t: 'message', id },
  { t: 'text', v: text },
  { t: 'message_end', id },
];

beforeEach(async () => {
  threadId = `thread-${++threadCount}`;
  stored = [];
  modelName = undefined;
  createThread.mockResolvedValue({ id: threadId, title: null, is_archived: false } as never);
  listThreads.mockResolvedValue([]);
  listMessages.mockImplementation(async () => stored as never);
});

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
  seen.aui = undefined;
  vi.resetAllMocks();
});

async function mount(): Promise<void> {
  rendered = await renderInto(withQueryClient(testQueryClient(), <ChatAssistant />));
  await flush();
}

describe('ChatAssistant, one turn of a new thread', () => {
  it('creates the thread, then streams the message to it under the id the page shows', async () => {
    modelName = 'gpt-test';
    await mount();
    serve(reply('a1', 'Hello.'), [{ id: 'a1', type: 'ai', content: 'Hello.' }]);
    await send('Hi');

    expect(createThread).toHaveBeenCalledTimes(1);
    const [options] = stream.mock.calls[0];
    expect(options).toMatchObject({ threadId, model: 'gpt-test', message: 'Hi', attachments: [] });
    expect(shown()[0]).toEqual({ id: options.messageId, role: 'user', text: 'Hi' });
  });

  it('sends attachments as plain text, without the label the attachment adapter adds', async () => {
    await mount();
    serve([]);
    const attachment: CompleteAttachment = {
      id: 'att-1',
      type: 'document',
      name: 'notes.md',
      contentType: 'text/markdown',
      status: { type: 'complete' },
      content: [{ type: 'text', text: 'Attached document "notes.md":\n\n# Notes\nBody' }],
    };
    const empty: CompleteAttachment = { ...attachment, id: 'att-2', name: 'empty.md', content: [] };
    await send('Read this', [attachment, empty]);

    expect(stream.mock.calls[0][0].attachments).toEqual([{ name: 'notes.md', text: '# Notes\nBody' }]);
  });

  it('once the turn is over, shows the stored copy in place of the streamed one', async () => {
    await mount();
    serve(reply('a1', 'Hello.'), [{ id: 'a1', type: 'ai', content: 'Hello from the server.' }]);
    await send('Hi');

    const userId = stream.mock.calls[0][0].messageId;
    expect(shown()).toEqual([
      { id: userId, role: 'user', text: 'Hi' },
      { id: 'a1', role: 'assistant', text: 'Hello from the server.' },
    ]);
    expect(isRunning()).toBe(false);
  });

  it('a second turn goes to the same thread and keeps the first in the history', async () => {
    await mount();
    serve(reply('a1', 'One.'), [{ id: 'a1', type: 'ai', content: 'One.' }]);
    await send('First');
    serve(reply('a2', 'Two.'), [{ id: 'a2', type: 'ai', content: 'Two.' }]);
    await send('Second');

    expect(createThread).toHaveBeenCalledTimes(1);
    expect(stream.mock.calls[1][0].threadId).toBe(threadId);
    expect(shown().map(({ role, text }) => `${role}: ${text}`)).toEqual([
      'user: First',
      'assistant: One.',
      'user: Second',
      'assistant: Two.',
    ]);
  });
});

describe('ChatAssistant, a turn that ends early', () => {
  it('stopping keeps what streamed so far, marked cancelled, after the stored user message', async () => {
    await mount();
    serveUntilAborted([
      { t: 'message', id: 'a1' },
      { t: 'text', v: 'Half an ans' },
    ]);
    await send('Hi');
    expect(isRunning()).toBe(true);
    expect(shown().map(({ id, role, text }) => ({ id, role, text }))).toEqual([
      { id: stream.mock.calls[0][0].messageId, role: 'user', text: 'Hi' },
      { id: 'a1', role: 'assistant', text: 'Half an ans' },
    ]);

    await act(async () => seen.aui!.thread().cancelRun());
    await flush();
    await flush();

    expect(shown()).toEqual([
      { id: stream.mock.calls[0][0].messageId, role: 'user', text: 'Hi' },
      { id: 'a1', role: 'assistant', text: 'Half an ans', status: { type: 'incomplete', reason: 'cancelled' } },
    ]);
    expect(isRunning()).toBe(false);
  });

  it('an error event ends the turn with its reason on the assistant message', async () => {
    await mount();
    serve([
      { t: 'message', id: 'a1' },
      { t: 'text', v: 'Partial' },
      { t: 'error', v: 'The model timed out.' },
      { t: 'text', v: ' never shown' },
    ]);
    await send('Hi');

    expect(shown()[1]).toEqual({
      id: 'a1',
      role: 'assistant',
      text: 'Partial',
      status: { type: 'incomplete', reason: 'error', error: 'The model timed out.' },
    });
    expect(isRunning()).toBe(false);
  });

  it('a request that fails before streaming shows the failure on an assistant message', async () => {
    await mount();
    stream.mockImplementationOnce(() => {
      throw new Error('Chat request failed with status 503');
    });
    await send('Hi');

    expect(shown().at(-1)).toMatchObject({
      role: 'assistant',
      text: '',
      status: { type: 'incomplete', reason: 'error', error: 'Chat request failed with status 503' },
    });
    expect(isRunning()).toBe(false);
  });

  // Bug: after a failure the page keeps only the assistant side of the turn, on the
  // assumption that the server stored the user message. A request refused before the
  // turn starts (offline, 401, 404, 5xx) stored nothing, so the message disappears.
  it.fails('a request that fails before streaming keeps the user message on screen', async () => {
    await mount();
    stream.mockImplementationOnce(() => {
      throw new Error('Chat request failed with status 503');
    });
    await send('Hi');

    expect(shown().map(({ role, text }) => `${role}: ${text}`)).toEqual(['user: Hi', 'assistant: ']);
  });

  // Bug: the same assumption when the turn completed but the stored copy could not be
  // fetched: the new user message is dropped, and with it gone the converter merges
  // this answer into the previous one.
  it.fails('keeps the whole streamed turn when the stored copy cannot be fetched afterwards', async () => {
    await mount();
    serve(reply('a1', 'One.'), [{ id: 'a1', type: 'ai', content: 'One.' }]);
    await send('First');
    listMessages.mockRejectedValue(new Error('offline'));
    serve(reply('a2', 'Two.'));
    await send('Second');

    expect(shown().map(({ role, text }) => `${role}: ${text}`)).toEqual([
      'user: First',
      'assistant: One.',
      'user: Second',
      'assistant: Two.',
    ]);
  });
});
